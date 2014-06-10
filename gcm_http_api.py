#!/usr/bin/python
# -*- coding: utf-8 -*-

import BaseHTTPServer
from argparse import ArgumentParser
import logging
from RESTHandler import RESTHandler, MissingParameterException, \
    ResourceNotFoundException
from gcm import setup_logging, GCMBackend, MySQL_schema_update


class GCMHandler(RESTHandler):
    """
    Endpoints tree:
    URL              | POST                 | GET          | DELETE
    /users           | Register new reg_id  | ø            | ø
    /aliases         | Create a new alias   | List aliases | Drop an alias
    /messages        | Post a new message   | ø            | ø
    """

    def __init__(self, *args, **kwargs):
        self.gcm = GCMBackend()
        RESTHandler.__init__(self, *args, **kwargs)

    def add_users(self, payload, **kwargs):
        if 'reg_id' not in kwargs:
            raise MissingParameterException('reg_id')
        return self.gcm.add_user(kwargs['reg_id'])

    def get_alias(self, **kwargs):
        if 'reg_id' not in kwargs:
            raise MissingParameterException('reg_id')
        found, user = self.gcm.user_get(kwargs['reg_id'])
        if not found:
            raise ResourceNotFoundException('reg_id')
        count, aliases = self.gcm.get_alias(user[0]['user_id'])
        if count == 0:
            aliases = []
        return [alias['alias'] for alias in aliases]

    def add_alias(self, payload, **kwargs):
        if 'reg_id' not in kwargs:
            raise MissingParameterException('reg_id')
        if 'alias' not in payload:
            raise MissingParameterException('alias')
        found, user = self.gcm.user_get(kwargs['reg_id'])
        if not found:
            raise ResourceNotFoundException('reg_id')
        success, new_id = self.gcm.add_alias(user[0]['user_id'],
                                             payload['alias'])
        return {'created': success}

    def del_alias(self, **kwargs):
        if 'reg_id' not in kwargs:
            raise MissingParameterException('reg_id')
        found, user = self.gcm.user_get(kwargs['reg_id'])
        if not found:
            raise ResourceNotFoundException('reg_id')
        return self.gcm.del_alias(user[0]['user_id'], kwargs['alias'])

    def add_messages(self, payload, **kwargs):
        return self.gcm.add_message(**payload)


def parse_args(print_help=False):
    parser = ArgumentParser(
        description='HTTP API to Google Cloud Messaging.')
    parser.add_argument('--port',
                        default=8080, type=int,
                        help='Port the HTTP API should listen.')
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
    server = BaseHTTPServer.HTTPServer(('', args.port), GCMHandler)
    server.serve_forever()
