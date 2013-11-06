import os
import logging

import argparse
import tornado.httpserver
import tornado.web
import tornado.ioloop
from tornado.ioloop import IOLoop
import tornado.log

from providers.google_fetch import G2RSS
from utils import config
from utils.config import getLogHandler

from handlers.feed import FeedHandler


class Application(tornado.web.Application):
    def __init__(self, args, logger):
        self.args = args

        handlers = [
            (r'/feed/??', FeedHandler, dict(logger=logger)),
        ]
        settings = dict(
            template_path=os.path.join(os.path.dirname(__file__), "templates"),
            static_path=os.path.join(os.path.dirname(__file__), "static"),
            debug=True,
            autoescape=None,
        )
        self.g2rss = G2RSS(os.path.join(os.path.dirname(__file__), "config"), logger)
        tornado.web.Application.__init__(self, handlers, **settings)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(prog='G+RSS')
    parser.add_argument('--port', required=True, type=int)
    parser.add_argument('--log_path', required=True)
    parser.add_argument('--max_results', default=4, type=int)
    args = parser.parse_args()

    logging.basicConfig(format='%(asctime)s %(message)s', datefmt='%m/%d/%Y %H:%M:%S')
    logger = logging.getLogger(__name__)

    logger.addHandler(getLogHandler(os.path.join(args.log_path, 'server.log')))
    logger.level = logging.INFO

    #create application
    application = Application(args, logger)

    #apply log config and launch
    tornado.log.access_log.addHandler(getLogHandler(os.path.join(args.log_path, 'access.log')))
    tornado.log.access_log.level = logging.INFO
    tornado.log.app_log.addHandler(getLogHandler(os.path.join(args.log_path, 'app.log')))
    tornado.log.app_log.level = logging.INFO
    tornado.log.gen_log.addHandler(getLogHandler(os.path.join(args.log_path, 'gen.log')))
    tornado.log.gen_log.level = logging.INFO
    http_server = tornado.httpserver.HTTPServer(application)
    http_server.listen(args.port)

    logger.info('Starting server v{0}'.format(config.version))
    logger.info('port={0}, log_path={1}, max_results={2}'.format(args.port, args.log_path, args.max_results))

    #run
    tornado.ioloop.IOLoop.instance().start()
