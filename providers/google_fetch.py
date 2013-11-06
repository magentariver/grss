import os
import json
import re
import time
from email import utils
from httplib import BadStatusLine
import calendar
from dateutil.parser import parse
from oauth2client.file import Storage
from oauth2client.client import SignedJwtAssertionCredentials
import httplib2
from apiclient import discovery
from apiclient import errors
import tornado.web


class RetryError(Exception):
    """Retry can be attempted"""
    pass


class G2RSS:
    def __init__(self, config_path, logger):
        self.logger = logger
        self.config_path = config_path
        self.service = None
        self.http = None
        self.auth_time = time.time()

        # Authenticate and construct service.
        # Prepare credentials, and authorize HTTP object with them.
        storage = Storage(os.path.join(config_path, 'plus.dat'))
        self.credentials = storage.get()

        if self.credentials is None or self.credentials.invalid:
            self.init_credentials(storage)

        #precompile regex
        self.re_img = re.compile('(/[^/]+\.jpg)')
        self.re_br = re.compile('\r\n|\n|\r')

    def init_credentials(self, storage):
        self.logger.warning('Invalid credentials')
        f_key = file(os.path.join(self.config_path, 'privatekey.p12'), 'rb')
        key = f_key.read()
        f_key.close()
        f_meta = file(os.path.join(self.config_path, 'client_secrets.json'), 'rb')
        data = json.load(f_meta)
        self.credentials = SignedJwtAssertionCredentials(
            data['web']['client_email'],
            key,
            scope='https://www.googleapis.com/auth/plus.me')
        self.credentials.set_store(storage)

    def authorize(self):
        if self.service is None or time.time() - self.auth_time > 300:
            self.logger.info('Authorizing credentials')
            self.http = self.credentials.authorize(http=httplib2.Http())
            # Construct a service object via the discovery service.
            self.service = discovery.build('plus', 'v1', http=self.http)
            self.auth_time = time.time()

    def get_activities_since(self, user_id, max_results, stamp):
        """
        returns activities only if update timestamp is greater than given stamp
        """
        activities_doc = self.get_activities(user_id, max_results)
        updated = calendar.timegm(parse(activities_doc['updated']))
        if updated <= stamp:
            return None
        return activities_doc

    def get_activities(self, user_id, max_results):
        try:
            if self.credentials is None or self.credentials.invalid:
                raise tornado.web.HTTPError(403, 'Invalid Credentials')
            self.authorize()

            # query data from google
            request = self.service.activities().list(userId=user_id, collection='public', maxResults=max_results)
            activities_doc = request.execute()
            if 'updated' in activities_doc:
                self.logger.info('Received data for [{0}], updated [{1}]'.format(user_id, activities_doc['updated']))
            else:
                self.logger.info('Received empty data set for [{0}]'.format(user_id))

        except errors.HttpError as e:
            self.logger.warning('HttpError: {0}'.format(e.resp))
            return None
            #raise RetryError()

        except BadStatusLine as e:
            self.logger.warning('BadStatusLine: {0}'.format(e.line))
            raise RetryError()

        except Exception as e:
            self.logger.warning('get_activities for [{0}]: exception: {1}:{2}'.format(user_id, type(e), e))
            return None

        return activities_doc

    def render(self, user_id, option='', max_results='4'):
        activities_doc = self.get_activities(user_id, max_results)
        # generate rss items
        return self.process_items(option, activities_doc)

    def result(self, guid, updated, url, title, description, full_image=''):
        return {
            'title': self.re_br.sub(' ', title),
            'link': url,
            'fullImage': full_image,
            'description': description,
            'guid': guid,
            'pubDate': utils.formatdate(calendar.timegm(parse(updated).timetuple()))
        }

    @staticmethod
    def get_reshare_description(item, description):
        if 'annotation' in item:
            annotation = item['annotation']
        else:
            annotation = u''
        description = u'{0} <br> \r\n {1} <br> \r\n{3} ({2}) via {5} ({4})'.format(
            annotation.replace(u'<br>', u'<br>\r\n'),
            description.replace(u'<br>', u'<br>\r\n'),
            item['url'],
            item['actor']['displayName'],
            item['object']['url'],
            item['object']['actor']['displayName'])
        return description

    def process_photo(self, item, share):
        description = item['object']['content']
        title = item['title'][:70]
        #google issue again?
        url = item['object']['attachments'][0]['url']
        if not url.startswith('https://plus.google.com'):
            url = 'https://plus.google.com' + url

        if 'fullImage' in item['object']['attachments'][0]:
            full_image = item['object']['attachments'][0]['fullImage']['url']
            # cater for Google's issue with not providing full-size image links
            if 'width' in item['object']['attachments'][0]['fullImage']:
                strdim = 'w{0}-h{1}'.format(item['object']['attachments'][0]['fullImage']['width'],
                                            item['object']['attachments'][0]['fullImage']['height'])
                if full_image.count(strdim) == 0:
                    full_image = self.re_img.sub('/s0\g<1>', full_image)

            #description += '<br/><img src="{0}" />'.format(fullImage)
            url = full_image
        else:
            full_image = url

        if share:
            description = self.get_reshare_description(item, description)
        return self.result(item['id'], item['updated'], url, title, description, full_image)

    def process_text(self, item, share):
        description = item['object']['content']
        title = item['title'][:70]
        url = item['object']['url']
        if share:
            description = self.get_reshare_description(item, description)
        return self.result(item['id'], item['updated'], url, title, description)

    def process_link(self, item, share):
        description = item['object']['content']
        if 'displayName' in item['object']['attachments'][0]:
            title = item['object']['attachments'][0]['displayName']
        else:
            title = item['title'][:70]
        if 'url' in item['object']['attachments'][0]:
            url = item['object']['attachments'][0]['url']
        elif 'url' in item['object']:
            url = item['object']['url']
        else:
            url = item['url']
        if 'fullImage' in item['object']['attachments'][0]:
            full_image = item['object']['attachments'][0]['fullImage']['url']
        else:
            full_image = ''
        if share:
            description = self.get_reshare_description(item, description)

        return self.result(item['id'], item['updated'], url, title, description, full_image)

    def process_album(self, item, share):
        description = item['object']['content']
        title = item['title'][:70]
        url = item['object']['attachments'][0]['url']
        if not url.startswith('https://plus.google.com'):
            url = 'https://plus.google.com' + url
        if share:
            description = self.get_reshare_description(item, description)
        return self.result(item['id'], item['updated'], url, title, description, url)

    def process_items(self, option, activities_doc):
        #logger.info('Processing: filter={0}'.format(filter))
        for item in activities_doc.get('items', []):

            if 'attachments' in item['object']:
                if 'objectType' in item['object']['attachments'][0]:
                    object_type = item['object']['attachments'][0]['objectType']
                else:
                    object_type = 'link'

                if object_type == 'photo':
                    if option and option.count('photo') == 0:
                        continue
                    yield self.process_photo(item, item['verb'] == 'share')

                elif object_type == 'album':
                    if option and option.count('links') == 0:
                        continue
                    yield self.process_album(item, item['verb'] == 'share')

                else:
                    if option and option.count('links') == 0:
                        continue
                    yield self.process_link(item, item['verb'] == 'share')

            else:
                if option and (option.count('links-') > 0 or option.count('photo') > 0):
                    continue
                yield self.process_text(item, item['verb'] == 'share')