#!/usr/bin/python
# -*- coding: utf-8 -*-

from argparse import ArgumentParser
import logging
import json
from gcm import GCMBackend
import cherrypy
from cherrypy import HTTPError


"""
Endpoints tree:
│
├── /user
│   ├── POST  Register the given reg_id
|   ├── /REG_ID
|   |   └── PUT   Register the given reg_id
│   └── /subscription
│       ├── GET    List chans REG_ID is listening
│       ├── PUT    Replace the whole subscriptions
│       ├── POST   Subscribe to a new channel
│       ├── DELETE Drop all subscriptions
│       └── /CHANNEL
│           ├── GET    Get infos about this subscription
│           ├── PUT    Subscribe to the given channel
│           └── DELETE Unsubscribe from this channel
└── /channel
    └── /CHANNEL
        └── POST Send a message to this channel

"""


def json_datetime_handler(obj):
    if hasattr(obj, 'isoformat'):
        return obj.isoformat()


@cherrypy.popargs('channel')
class Channel(object):
    exposed = True

    def GET(self, channel):
        gcm = cherrypy.thread_data.gcm
        return json.dumps(gcm.channel.list_messages(channel),
                          default=json_datetime_handler)

    @cherrypy.tools.accept(media='text/plain')
    def POST(self, channel):
        gcm = cherrypy.thread_data.gcm
        content_length = min(int(cherrypy.request.headers['Content-Length']),
                             4096)
        rawbody = cherrypy.request.body.read(content_length)
        if len(rawbody) == 0:
            return json.dumps({'error': 'Empty body.'})
        return json.dumps(gcm.message.add(rawbody, channel))


@cherrypy.popargs('channel')
class Subscription(object):
    exposed = True

    def list_subscriptions(self, reg_id):
        gcm = cherrypy.thread_data.gcm
        found, user = gcm.user.get(reg_id)
        if not found:
            raise HTTPError(404, 'reg_id not found')
        count, channels = gcm.channel.list_subscriptions(user[0]['user_id'])
        if count == 0:
            channels = []
        return [channel['name'] for channel in channels]

    def GET(self, reg_id, channel=None):
        if channel is None:
            return json.dumps(self.list_subscriptions(reg_id))
        else:
            # May retrieve info about this subscription ?
            return json.dumps({'error': 'No info for a subscription yet.'})

    def PUT(self, reg_id, channel=None):
        if channel is None:
            # May create a whole bunch of given channels
            return json.dumps({'error': 'Multi channel subscription '
                               'unsupported'})
        gcm = cherrypy.thread_data.gcm
        found, user = gcm.user.get(reg_id)
        if not found:
            raise HTTPError(404, 'reg_id not found')
        success, new_id = gcm.channel.subscribe(user[0]['user_id'], channel)
        return json.dumps({'created': success})

    def DELETE(self, reg_id, channel=None):
        if channel is None:
            # May delete the entier list of subscription
            return json.dumps({'error': 'Multi channel deletion '
                               'unsupported yet'})
        gcm = cherrypy.thread_data.gcm
        found, user = gcm.user.get(reg_id)
        if not found:
            raise HTTPError(404, 'reg_id not found')
        return json.dumps(gcm.channel.unsubscribe(user[0]['user_id'], channel))


@cherrypy.popargs('reg_id')
class User(object):
    exposed = True
    subscription = Subscription()

    def PUT(self, reg_id):
        return json.dumps(cherrypy.thread_data.gcm.user.add(reg_id))

    def POST(self, reg_id):
        return json.dumps(cherrypy.thread_data.gcm.user.add(reg_id))


class KISSPushHTTP(object):
    exposed = True
    user = User()
    channel = Channel()

    def GET(self):
        return 'KISSPush'


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
    def on_new_thread(thread_id):
        cherrypy.thread_data.gcm = GCMBackend()
    args = parse_args()
    cherrypy.config.update({'server.socket_port': args.port,
                            'server.socket_host': '0.0.0.0'})
    cherrypy.engine.subscribe('start_thread', on_new_thread)
    cherrypy.quickstart(
        KISSPushHTTP(),
        config={'/': {'request.dispatch':
                          cherrypy.dispatch.MethodDispatcher()}})
