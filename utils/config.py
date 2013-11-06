import logging
from logging import handlers

def getLogHandler(file_name):
    channel = handlers.RotatingFileHandler(file_name, maxBytes=262144, backupCount=5)
    channel.setFormatter(logging.Formatter("%(asctime)s\t%(levelname)s\t[%(message)s]", "%Y-%m-%d %H:%M:%S"))
    return channel

version = '0.5.0'

MAX_RESULTS = 6             # max items to fetch from google
