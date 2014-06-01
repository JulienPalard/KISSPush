#!/usr/bin/python

import json
import requests
from config import config
from argparse import ArgumentParser
import logging
from time import sleep
from gcm import messages_to_send, setup_logging, MySQL_schema_update


def pusher():
    while True:
        try:
            push_all()
            sleep(.5)
        except Exception:
            logging.getLogger('kisspush').exception(
                "Unhandled exception while pushing messages to GCM")


def push_all():
    todo = messages_to_send()
    for message in todo:
        try:
            push_one(message)
        except Exception:
            logging.getLogger('kisspush').exception(
                "Unhandled exception while pushing a message to GCM")


def push_one(message):
    """
    TODO Group by id_message, do not send them 1 by 1, google support
    batch send of the same message.
    """
    data = {'registration_ids': [message['registration_id']],
            'data': {'msg': message['message']}}
    headers = {'Content-Type': 'application/json',
               'Authorization': 'key=' + config['api_key']}
    url = 'https://android.googleapis.com/gcm/send'
    try:
        response = requests.post(url, data=json.dumps(data), headers=headers)
    except Exception:
        logging.getLogger('kisspush').exception("Sending a message to GCM")
    else:
        logging.getLogger('kisspush').info(response.content)


def parse_args(print_help=False):
    parser = ArgumentParser(
        description='Backend to push messages to Google Cloud Messaging.')
    parser.add_argument('--syslog',
                        default=False, action='store_true',
                        help='Log into syslog using /dev/log')
    parser.add_argument('--verbose',
                        default=logging.INFO,
                        action='store_const',
                        const=logging.DEBUG,
                        help='Log debug messages')
    if print_help:
        parser.print_help()
    return parser.parse_args()


if __name__ == '__main__':
    args = parse_args()
    logger = setup_logging(args.verbose, args.syslog)
    MySQL_schema_update()
    pusher()
