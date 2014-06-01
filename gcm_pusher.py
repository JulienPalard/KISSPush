#!/usr/bin/python

import json
import requests
from config import config
from argparse import ArgumentParser
import logging
from time import sleep
from gcm import messages_to_send, setup_logging, MySQL_schema_update, \
    message_update, user_update


class GCM_Pusher():
    def __init__(self):
        self.backoff = 0
        self.log = logging.getLogger('kisspush')
        self.headers = {'Content-Type': 'application/json',
                        'Authorization': 'key=' + config['api_key']}
        self.url = 'https://android.googleapis.com/gcm/send'

    def run(self):
        while True:
            try:
                self.push_all()
                if self.backoff > 0:
                    sleep(self.backoff)
                sleep(.5)
            except Exception:
                self.log.exception(
                    "Unhandled exception while pushing messages to GCM")

    def push_all(self):
        todo = messages_to_send()
        for message in todo:
            try:
                self.push_one(message)
            except Exception:
                logging.getLogger('kisspush').exception(
                    "Unhandled exception while pushing a message to GCM")

    def exponential_backoff(self, response):
        retry_after = response.headers.get('Retry-After', None)
        if retry_after is not None:
            self.backoff = int(retry_after)
        elif response == 200:
            self.backoff = 0
        elif response.status_code >= 500:
            self.backoff = 1 if self.backoff == 0 else self.backoff * 2
            self.log.info("Will backoff %d seconds after receiving a %d error",
                          self.backoff, response.status_code)

    def handle_result(self, result, registration_id):
        if 'error' in result:
            if result['error'] == "InvalidRegistration":
                user_update({'valid': 0},
                            registration_id=registration_id)
        print registration_id, result

    def push_one(self, message):
        data = {'registration_ids': message['registration_ids'],
                'data': {'msg': message['message']},
                'dry_run': True}
        if message['collapse_key'] is not None:
            data['collapse_key'] = message['collapse_key']
        if message['delay_while_idle']:
            message['delay_while_idle'] = True
        data = json.dumps(data)
        self.log.debug("Will send %s", data)
        try:
            response = requests.post(self.url, data=data, headers=self.headers)
            self.exponential_backoff(response)
        except Exception:
            self.log.exception("While sending a message to GCM")
        else:
            parsed_response = response.json()
            message_update({'multicast_id': parsed_response['multicast_id']},
                           message_id=message['message_id'])

            for i, result in enumerate(parsed_response['results']):
                self.handle_result(result, message['registration_ids'][i])
            # {"multicast_id":1821716262194746,"success":1,"failure":0,
            #   "canonical_ids":0,
            #   "results":[{"message_id":
            #               "0:1063362409caf9fed"}]}

            self.log.info(response.content)


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
    GCM_Pusher().run()
