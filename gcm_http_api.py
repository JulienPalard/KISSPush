#!/usr/bin/python

import BaseHTTPServer
import cgi
import json
import urlparse
from argparse import ArgumentParser
import logging
from gcm import setup_logging, user_create, alias_get, alias_create, \
    message_create, MySQL_schema_update


class GCMHandler(BaseHTTPServer.BaseHTTPRequestHandler):
    def do_GET(self):
        params = urlparse.parse_qs(urlparse.urlparse(self.path).query)
        if self.path.startswith("/alias"):
            return self.alias_get(params)
        self.send_response(500)

    def do_POST(self):
        (content_type, dict) = cgi.parse_header(
            self.headers.getheader('content-type'))
        if content_type == 'multipart/form-data':
            params = cgi.parse_multipart(self.rfile, dict)
        elif content_type == 'application/x-www-form-urlencoded':
            length = int(self.headers.getheader('content-length'))
            params = cgi.parse_qs(self.rfile.read(length), keep_blank_values=1)
        else:
            params = {}
        if self.path == "/register":
            return self.register(params)
        if self.path == "/send":
            return self.send(params)
        if self.path == "/alias":
            return self.alias(params)

        self.send_response(500)

    def param_get(self, params, name, default):
        try:
            value = params[name][0].strip()
            if len(value) > 0:
                return value
        except (ValueError, IndexError):
            pass
        return default

    def register(self, params):
        """
        Stores the registration id sent via the 'reg_id' parameter

        Sample request:
        curl -d "reg_id=test_id" http://localhost:8080/register
        """
        reg_id = self.param_get(params, 'reg_id', None)
        if reg_id is None:
            self.send_response(400)
        user_create(reg_id)
        self.send_response(200)

    def alias_get(self, params):
        reg_id = self.param_get(params, 'reg_id', None)
        if reg_id is None:
            self.send_response(500)
            return
        count, aliases = alias_get(reg_id)
        alias_list = [alias['alias'] for alias in aliases]
        self.wfile.write(json.dumps(alias_list))
        self.send_response(200)

    def alias(self, params):
        """
        Stores the given alias for the goven registration id.

        Sample request:
        curl -d "reg_id=test_id&alias=me" http://localhost:8080/alias
        """
        reg_id = self.param_get(params, 'reg_id', None)
        alias = self.param_get(params, 'alias', None)
        if reg_id is None or alias is None:
            self.send_response(400)
        if alias_create(reg_id, alias) is not None:
            self.send_response(200)
        else:
            self.send_response(404)

    def send(self, params):
        """
        Message is specified by the 'msg' parameter.
        Devices are specified indirectly by the alias given in the
        `to` parameter.

        Sample request:
        curl -d "to=me&msg=Hello" http://localhost:8080/send
        """

        msg = self.param_get(params, 'msg', None)
        to = self.param_get(params, 'to', None)
        collapse_key = self.param_get(params, 'collapse_key', None)
        delay_while_idle = self.param_get(params, 'delay_while_idle', False)
        if msg is None or to is None:
            self.send_response(500)
            return
        self.wfile.write(json.dumps(message_create(msg, to, collapse_key,
                                                   delay_while_idle)))
        self.send_response(200)


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
