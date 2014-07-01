KISSPush
========

:Author: Julien Palard

Code Structure
--------------

KISSPush is structured in two major parts:

 * The Android client, in the /android/ directory.
 * The server part, in the /server/ directory.

Android Client
--------------

The Android Client is a basic android project with two views,
subscriptions and channels. It uses the GCM service provided by the
Play Services lib.

Server
------

The server is composed of two independent parts:

 * The HTTP server, exposing a JSON, maybe REST, API.
 * The "GCM pusher", a part pushing to Google Cloud Messaging.

The separation of concerns is usefull here to open the path to
implement an APNS pusher, an SMS pusher... Also your pusher can crash
without crashing the API, no message are lost in this case.

HTTP API
--------

Here is the endpoint tree of the HTTP API::

    api.kisspush.net
    │
    ├── /user
    │   ├── POST  Register the given reg_id
    │   ├── /REG_ID
    │   │   └── PUT   Register the given reg_id
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
