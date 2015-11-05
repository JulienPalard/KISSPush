#!/usr/bin/env python3

import logging
import warnings
import pymysql
import sys

logger = logging.getLogger(__name__)

"""
The big picture:
 * Two processes:
    -> HTTP Server, storing messages in MySQL, that's all
    -> Sender, pulling from MySQL and pushing to GCM

The sender may be multithreade following this model:
 * A single master thread pulling from MySQL, updating message.status
   from todo to done, dispatching messages to workers.
 * Worker threads, getting jobs from master thread, updating message.status
   from done to todo, message.retry_after, and message.number_of_failures
   if the message have to be resent.

"""


class MySQLBackend():
    def __init__(self, host, user, password, db):
        self.link = pymysql.connect(host, user, password, db,
                                    charset='utf8', autocommit=True)

    def mysql_schema_update(self):
        """Apply schema changes from mysql_schema.py.
        Typically used the first time to create the whole schema.
        """
        from mysql_schema import MYSQL_SCHEMA
        with self.link.cursor() as cursor:
            initial_config = """
            CREATE TABLE IF NOT EXISTS schema_history
            (
                `statement` VARCHAR(4096) NOT NULL,
                PRIMARY KEY (`statement`(767))
            ) ENGINE=InnoDB DEFAULT CHARSET=ascii COLLATE=ascii_bin
            """
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                cursor.execute(initial_config)
            for statement in MYSQL_SCHEMA:
                stmt = "SELECT 1 FROM schema_history WHERE statement = %s"
                cursor.execute(stmt, statement)
                if cursor.fetchone() is None:
                    try:
                        cursor.execute(statement)
                        cursor.execute("INSERT INTO schema_history VALUES(%s)",
                                       statement)
                    except Exception as ex:
                        logger.error("Got an exeption executing %s",
                                     statement)
                        logger.exception(ex)
                        sys.exit(1)

    def query(self, statement, args=None):
        try:
            with self.link.cursor() as cursor:
                modified = cursor.execute(statement, args)
                desc = [col[0] for col in cursor.description]
                result = [dict(list(zip(desc, data))) for
                          data in cursor.fetchall()]
            return modified, result
        except Exception as e:
            logger.exception("%s while querying statement %s with %s ",
                             e, statement, repr(args))

    def execute(self, statement, args=None):
        try:
            with self.link.cursor() as cursor:
                modified = cursor.execute(statement, args)
                result = self.link.insert_id()
            return modified, result
        except Exception as e:
            self.link.rollback()
            logger.exception("%s while executing statement %s with %s ",
                             e, statement, repr(args))

    def update(self, table, update_set, conditions):
        sql_set = []
        sql_values = []
        sql_where = []
        for key, value in update_set.items():
            sql_set.append("%s = %%s" % key)
            sql_values.append(value)
        for key, value in conditions.items():
            sql_where.append("%s = %%s" % key)
            sql_values.append(value)
        return self.execute(
            ("UPDATE " + table + " SET " + ', '.join(sql_set) +
             " WHERE " + ' AND '.join(sql_where)), sql_values)


class GCMBackendUser():
    def __init__(self, gcm):
        self.gcm = gcm

    def add(self, reg_id):
        """Store (or update the last seen time) a new reg_id.
        """
        return self.gcm.db.execute(
            """INSERT INTO user (registration_id, ctime, ltime)
               VALUES (%s, NOW(), NOW())
         ON DUPLICATE KEY UPDATE ltime = VALUES(ltime), valid=1""",
            reg_id)

    def get(self, reg_id=None, user_id=None, channel=None):
        """Get a user, given its reg_id, or user_id, or channel.
        """
        where = ['user.valid = 1']
        args = []
        if reg_id is None and user_id is None and channel is None:
            raise Exception('Missing parameter')
        if reg_id is not None:
            self.add(reg_id)
            where.append("user.registration_id = %s")
            args.append(reg_id)
        if user_id is not None:
            where.append("user.user_id = %s")
            args.append(user_id)
        if channel is not None:
            where.append("channel.name = %s")
            args.append(channel)
        return self.gcm.db.query(
            """SELECT user.user_id, user.registration_id, user.ctime,
                      user.ltime, channel.name AS channel
                 FROM user
            LEFT JOIN subscription USING(user_id)
            LEFT JOIN channel USING(channel_id)
                WHERE """ + ' AND '.join(where), args)

    def reg_id_changed(self, old_reg_id, new_reg_id):
        """Update the given reg_id.
        """
        self.add(new_reg_id)
        found_old, old_user = self.get(old_reg_id)
        found_new, new_user = self.get(new_reg_id)
        if found_old and found_new:
            self.gcm.db.execute("""
            INSERT IGNORE INTO subscription
                   SELECT %s, channel_id FROM subscription
                    WHERE user_id = %s
            """, (new_user[0]['user_id'], old_user[0]['user_id']))
        if found_old:
            self.gcm.db.execute(
                """UPDATE user SET valid = 0
                    WHERE user_id = %s""",
                old_user[0]['user_id'])

    def update(self, update_set, reg_id):
        return self.gcm.db.update(
            'user', update_set, {'registration_id': reg_id})


class GCMBackendChannel():
    def __init__(self, gcm):
        self.gcm = gcm

    def create(self, name):
        return self.gcm.db.execute(
            """INSERT INTO channel(name) VALUES (%s)
              ON DUPLICATE KEY UPDATE
                channel_id = LAST_INSERT_ID(channel_id)""",
            name)

    def subscribe(self, user_id, name):
        _, channel_id = self.create(name)
        return self.gcm.db.execute(
            """INSERT IGNORE INTO subscription (user_id, channel_id)
               VALUES (%s, %s)""",
            (user_id, channel_id))

    def list_subscriptions(self, user_id):
        return self.gcm.db.query(
            """SELECT name FROM subscription
                 JOIN channel USING (channel_id)
                WHERE user_id = %s""",
            user_id)

    def unsubscribe(self, user_id, name):
        _, channel_id = self.create(name)
        return self.gcm.execute(
            """DELETE FROM subscription
                WHERE user_id = %s AND channel_id = %s""",
            (user_id, channel_id))

    def list_messages(self, channel):
        return self.gcm.query(
            """SELECT message, ctime FROM message
                 JOIN channel USING (channel_id)
                WHERE channel.name = %s
             ORDER BY ctime DESC
                LIMIT 10""",
            channel)


class GCMBackendMessage():
    def __init__(self, gcm):
        self.gcm = gcm

    def add(self, message, to_channel, collapse_key=None,
            delay_while_idle=True):
        _, channel_id = self.gcm.channel.create(to_channel)
        _, message_id = self.gcm.db.execute(
            """INSERT INTO message (message, retry_after,
                      collapse_key, delay_while_idle, channel_id,
                      ctime)
               VALUES (%s, NOW(), %s, %s, %s, NOW())""",
            (message, collapse_key,
             1 if delay_while_idle else 0, channel_id))
        qte, recipients = self.gcm.user.get(channel=to_channel)
        for recipient in recipients:
            self.gcm.db.execute(
                """INSERT INTO recipient (message_id, user_id)
                   VALUES (%s, %s)""",
                (message_id, recipient['user_id']))
        return {'message_id': message_id, 'clients': qte}

    def to_send(self):
        count, todo = self.gcm.db.query(
            """SELECT message.message_id,
              message.message,
              message.collapse_key,
              message.delay_while_idle,
              GROUP_CONCAT(user.registration_id SEPARATOR 0x1D)
                AS registration_ids
         FROM message
         JOIN recipient USING (message_id)
         JOIN user USING (user_id)
        WHERE message.status = "todo"
              AND retry_after < NOW()
              AND user.valid = 1
     GROUP BY message.message_id""")
        for each in todo:
            each['registration_ids'] = each['registration_ids'].split('\x1D')
        if count > 0:
            ids = [str(message['message_id']) for message in todo]
            self.gcm.db.execute(
                """UPDATE message SET status = 'done'
                    WHERE message_id IN (""" + ','.join(ids) + ")")
        return todo

    def update(self, update_set, message_id):
        return self.gcm.db.update('message', update_set,
                                  {'message_id': message_id})


class GCMBackend():
    """Storage abstraction for messages.
    """
    def __init__(self):
        from config import config
        self.db = MySQLBackend(host=config['mysql']['host'],
                               user=config['mysql']['user'],
                               password=config['mysql']['password'],
                               db=config['mysql']['db'])
        self.user = GCMBackendUser(self)
        self.channel = GCMBackendChannel(self)
        self.message = GCMBackendMessage(self)
