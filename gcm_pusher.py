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

    def handle_result(self, message_id, registration_id, result):
        # If message_id is set, check for registration_id:
        if 'message_id' in result:
            # If registration_id is set,
            if 'registration_id' in result:
                # replace the original ID with the new value
                # (canonical ID) in your server database. Note that
                # the original ID is not part of the result, so you
                # need to obtain it from the list of registration_ids
                # passed in the request (using the same index).
                user_update({'registration_id': result['registration_id']},
                            registration_id=registration_id)
        elif 'error' in result:  # Otherwise, get the value of error:
            if result['error'] == 'Unavailable':
                # If it is Unavailable, you could retry to send it in
                # another request.
                # TODO
                pass
            elif result['error'] == "InvalidRegistration":
                # If it is NotRegistered, you should remove the
                # registration ID from your server database because
                # the application was uninstalled from the device or
                # it does not have a broadcast receiver configured to
                # receive com.google.android.c2dm.intent.RECEIVE
                # intents.
                user_update({'valid': 0},
                            registration_id=registration_id)
            elif result['error'] == "MissingRegistration":
                self.log.error("Oops, missing registration id in message %d ?",
                               message_id)
            elif result['error'] == 'MismatchSenderId':
                self.log.error("Oops, mismatching sender id in message %d "
                               "Dropping registration_id %s, won't work again "
                               "if you switched sender_id.",
                               message_id, registration_id)
                user_update({'valid': 0},
                            registration_id=registration_id)
            elif result['error'] == "NotRegistered":
                self.log.error("Oops, registration_id seems not registered, "
                               "in message %d."
                               "Dropping registration_id %s.",
                               message_id, registration_id)
                user_update({'valid': 0},
                            registration_id=registration_id)
            elif result['error'] == 'MessageTooBig':
                self.log.error("Oops, message %d too big.", message_id)
            elif result['error'] == 'InvalidTtl.':
                self.log.error("Oops, invalid TTL for message %d.", message_id)
            elif result['error'] == 'InvalidDataKey':
                self.log.error("Oops, payload contains an invalid data key "
                               "in message %d.", message_id)
            elif result['error'] == 'InvalidPackageName':
                self.log.error("Oops, invalid package name "
                               "for message %d.", message_id)
            elif result['error'] == 'InternalServerError':
                self.log.error("Oops, got an Internal Server Error from GCM, "
                               "for message %d.", message_id)



            else:
                # Otherwise, there is something wrong in the
                # registration ID passed in the request; it is
                # probably a non-recoverable error that will also
                # require removing the registration from the server
                # database. See Interpreting an error response for all
                # possible error values.
                self.log.error("%s from GCM servers, "
                               "marking user as invalid.", result['error'])
                user_update({'valid': 0},
                            registration_id=registration_id)

    def push_one(self, message):
        data = {'registration_ids': message['registration_ids'],
                'data': {'msg': message['message']}}
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

            # If the value of failure and canonical_ids is 0, it's not
            # necessary to parse the remainder of the
            # response.
            if ((parsed_response['failure'] > 0 or
                 parsed_response['canonical_ids'] > 0)):
                # Otherwise, we recommend that you iterate
                # through the results field and do the following for each
                # object in that list:
                for i, result in enumerate(parsed_response['results']):
                    self.handle_result(message['message_id'],
                                       message['registration_ids'][i], result)
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
