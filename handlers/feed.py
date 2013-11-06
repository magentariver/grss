import json
import time
from email import utils
import tornado
from tornado import gen
from tornado import web
from tornado.ioloop import IOLoop
from utils import config


class FeedHandler(tornado.web.RequestHandler):
    def initialize(self, logger):
        self.logger = logger

    @tornado.web.asynchronous
    @gen.coroutine
    def get(self):
        self.set_header('Content-Type', 'application/rss+xml;charset=utf-8')
        gid = self.get_argument('gid')
        filter_arg = self.get_argument('filter', '')
        self.logger.info('Request: {0},{1}'.format(gid, filter_arg))

        items = self.application.g2rss.render(gid, option=filter_arg)
        self.render('feed.xml', version=config.version, gid=gid, pubDate=utils.formatdate(), items=items, filter=filter_arg)
