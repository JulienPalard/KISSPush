#!/usr/bin/python3

"""Module dedicated to send messages to Google Clound Messaging.
"""

import json
import requests
from argparse import ArgumentParser
import logging
from time import sleep
from gcm import GCMBackend

logger = logging.getLogger(__name__)


class GCMPusher(object):
    """Glue between MySQL and GCM:
    while True:
        Fetch from MySQL,
        Push to GCM
    """

    def __init__(self, gcm_backend, api_key):
        self.backoff = 0
        self.db = gcm_backend
        self.headers = {'Content-Type': 'application/json',
                        'Authorization': 'key=' + api_key}
        self.url = 'https://android.googleapis.com/gcm/send'

    def run(self):
        """Infinite loop, fetching from MySQL, pushing to GCM.
        """
        while True:
            try:
                self.push_all()
                if self.backoff > 0:
                    sleep(self.backoff)
            except Exception:
                logger.exception(
                    "Unhandled exception while pushing messages to GCM")
            finally:
                sleep(.5)

    def push_all(self):
        """Fetch all messages to send from MySQL, push them one by one to GCM.
        """
        for message in self.db.message.to_send():
            self.push_one(message)

    def exponential_backoff(self, response):
        """Parses the backoff duration GCM asks us to wait,
        Backoff exponentially if GCM returns error code in the 500 range.
        """
        retry_after = response.headers.get('Retry-After', None)
        if retry_after is not None:
            self.backoff = int(retry_after)
        elif response == 200:
            self.backoff = 0
        elif response.status_code >= 500:
            self.backoff = 1 if self.backoff == 0 else self.backoff * 2
            logger.info("Will backoff %d seconds after receiving a %d error",
                        self.backoff, response.status_code)

    def handle_result(self, message_id, registration_id, result):
        """Directly implemented from the documentation, which is presented
        inline, this method parses the response of a GCM call, which can be:
         - A need to update a registration_id
         - An error
         - Or everything's ok, sometimes
        """
        # If message_id is set, check for registration_id:
        if 'message_id' in result:
            # If registration_id is set,
            if 'registration_id' in result:
                # replace the original ID with the new value
                # (canonical ID) in your server database. Note that
                # the original ID is not part of the result, so you
                # need to obtain it from the list of registration_ids
                # passed in the request (using the same index).
                logger.info("reg_id changed from %s to %s",
                            registration_id, result['registration_id'])
                self.db.user.reg_id_changed(registration_id,
                                            result['registration_id'])
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
                self.db.user.update({'valid': 0},
                                    registration_id)
            elif result['error'] == "MissingRegistration":
                logger.error("Oops, missing registration id in message %d ?",
                             message_id)
            elif result['error'] == 'MismatchSenderId':
                logger.error("Oops, mismatching sender id in message %d "
                             "Dropping registration_id %s, won't work again "
                             "if you switched sender_id.",
                             message_id, registration_id)
                self.db.user.update({'valid': 0},
                                    registration_id)
            elif result['error'] == "NotRegistered":
                logger.error("Oops, registration_id seems not registered, "
                             "in message %d."
                             "Dropping registration_id %s.",
                             message_id, registration_id)
                self.db.user.update({'valid': 0},
                                    registration_id)
            elif result['error'] == 'MessageTooBig':
                logger.error("Oops, message %d too big.", message_id)
            elif result['error'] == 'InvalidTtl.':
                logger.error("Oops, invalid TTL for message %d.", message_id)
            elif result['error'] == 'InvalidDataKey':
                logger.error("Oops, payload contains an invalid data key "
                             "in message %d.", message_id)
            elif result['error'] == 'InvalidPackageName':
                logger.error("Oops, invalid package name "
                             "for message %d.", message_id)
            elif result['error'] == 'InternalServerError':
                logger.error("Oops, got an Internal Server Error from GCM, "
                             "for message %d.", message_id)
            else:
                # Otherwise, there is something wrong in the
                # registration ID passed in the request; it is
                # probably a non-recoverable error that will also
                # require removing the registration from the server
                # database. See Interpreting an error response for all
                # possible error values.
                logger.error("%s from GCM servers, "
                             "marking user as invalid.", result['error'])
                self.db.user.update({'valid': 0},
                                    registration_id)

    def push_one(self, message):
        """Push the given message to GCM servers.
        A message is a dict containing:
         - message_id
         - registration_ids
         - message
         - An optional collapse_key
         - boolean delay_while_idle
        """
        data = {'registration_ids': message['registration_ids'],
                'data': {'msg': message['message']}}
        if message['collapse_key'] is not None:
            data['collapse_key'] = message['collapse_key']
        data['delay_while_idle'] = bool(message['delay_while_idle'])
        data = json.dumps(data)
        logger.debug("Will send %s", data)
        try:
            response = requests.post(self.url, data=data, headers=self.headers)
            self.exponential_backoff(response)
        except Exception:
            logger.exception("While sending a message to GCM")
        else:
            parsed_response = response.json()
            self.db.message.update({'multicast_id':
                                    parsed_response['multicast_id']},
                                   message_id=message['message_id'])
            logger.info("Raw response from GCM: %s", response.content)
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


def parse_args():
    """Parse command line arguments.
    """
    parser = ArgumentParser(
        description='Backend to push messages to Google Cloud Messaging.')
    parser.add_argument('--syslog',
                        default=False, action='store_true',
                        help='Log into syslog using /dev/log')
    parser.add_argument('--verbose',
                        default=logging.INFO,
                        dest='log_level',
                        action='store_const',
                        const=logging.DEBUG,
                        help='Log debug messages')
    return parser.parse_args()


def main(log_level=logging.INFO, syslog=False):
    """Called with command line arguments.
    """
    from logging import handlers
    from config import config
    logger.addHandler(handlers.SysLogHandler(address='/dev/log') if syslog
                      else logging.StreamHandler())
    logger.setLevel(log_level)
    logging.getLogger('gcm').addHandler(
        logging.StreamHandler())
    logging.getLogger('gcm').setLevel(logging.DEBUG)
    gcm_backend = GCMBackend()
    gcm_backend.db.mysql_schema_update()
    GCMPusher(gcm_backend, config['api_key']).run()

if __name__ == '__main__':
    main(**vars(parse_args()))
