#!/usr/bin/python
# -*- coding: utf-8 -*-

import sys
import BaseHTTPServer
import cgi
import json
import urlparse
import traceback


class RESTException(Exception):
    pass


class MissingParameterException(RESTException):
    pass


class ResourceNotFoundException(RESTException):
    pass


class RESTHandler(BaseHTTPServer.BaseHTTPRequestHandler):
    def log_exception(self):
        exc_type, exc_value, exc_traceback = sys.exc_info()
        lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
        self.log_error(''.join(lines))

    def dispatch(self, method, payload=None):
        url = urlparse.urlparse(self.path)
        path = url.path[1:].rstrip('/')
        method = method.lower()
        to_call = '_'.join((method, path))
        if not hasattr(self, to_call):
            self.send_response(400, "Unknown endpoint")
            self.end_headers()
            return
        try:
            query = dict(urlparse.parse_qsl(url.query))
            if method in ('get', 'del'):
                response = getattr(self, to_call)(**query)
            else:
                response = getattr(self, to_call)(payload, **query)
            self.send_response(200)
            self.end_headers()
            self.wfile.write(json.dumps(response))
        except MissingParameterException as ex:
            self.send_response(400, "Missing parameter: %s" % ex)
            self.end_headers()
        except ResourceNotFoundException as ex:
            self.send_response(404, "%s not found" % ex)
            self.end_headers()
        except Exception:
            self.log_exception()
            self.send_response(500)
            self.end_headers()

    def do_GET(self):
        self.dispatch('get')

    def do_POST(self):
        (content_type, values) = cgi.parse_header(
            self.headers.getheader('content-type'))
        length = int(self.headers.getheader('content-length'))
        payload = None
        if content_type == 'multipart/form-data':
            payload = dict(
                (key, value[0]) for key, value
                in cgi.parse_multipart(self.rfile, values).iteritems())
        elif content_type == 'application/x-www-form-urlencoded':
            payload = dict(cgi.parse_qsl(self.rfile.read(length),
                                         keep_blank_values=1))
        else:
            try:
                paylad = json.loads(self.rfile.read(length))
            except:
                self.log_exception()
                self.send_response(400, "Malformed JSON")
                self.end_headers()
                return
        self.dispatch('add', payload)

    def do_DELETE(self):
        self.dispatch('del')
