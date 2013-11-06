import argparse
import json
import logging
import os
from email import utils
from tornado.template import Template
from providers.google_fetch import G2RSS
from utils.config import version, getLogHandler

parser = argparse.ArgumentParser(prog='G+RSS.Poller')
parser.add_argument('--log_path', required=True)
args = parser.parse_args()

logging.basicConfig(format='%(asctime)s %(message)s', datefmt='%m/%d/%Y %H:%M:%S')
logger = logging.getLogger(__name__)
logger.addHandler(getLogHandler(os.path.join(args.log_path, 'test_google.log')))
logger.level = logging.INFO

f = open('templates/feed.xml')
tmpl = Template(f.read())
f.close()
json_data=open('data/plus_sample.json')
data = json.load(json_data)
#print(data)
grss = G2RSS(os.path.join(os.path.curdir, 'config'), logger)
#items = grss.render('107309481618797506810')
filter = ''
items = grss.process_items(filter, data)
print(tmpl.generate(version=version, gid='UNIT_TEST', pubDate=utils.formatdate(), items=items, filter=filter))