#!/usr/bin/env python

from mysql_schema import mysql_schema
from config import config
import logging
import MySQLdb

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


def setup_logging(level=logging.WARNING, syslog=False):
    logger = logging.getLogger('kisspush')
    if syslog:
        handler = logging.handlers.SysLogHandler(address='/dev/log')
    else:
        handler = logging.StreamHandler()
    formatter = logging.Formatter('kisspush %(asctime)-15s %(message)s', None)
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(level)
    return logger


def MySQL_schema_update():
    link = MySQLdb.connect(config['mysql']['host'],
                           config['mysql']['user'],
                           config['mysql']['password'],
                           config['mysql']['db'],
                           charset='utf8')
    link.autocommit(True)
    c = link.cursor()

    initial_config = """
    CREATE TABLE IF NOT EXISTS schema_history
    (
        `statement` VARCHAR(4096) NOT NULL,
        PRIMARY KEY (`statement`(767))
    ) ENGINE=InnoDB DEFAULT CHARSET=ascii COLLATE=ascii_bin
    """
    c.execute(initial_config)
    for statement in mysql_schema:
        stmt = "SELECT 1 FROM schema_history WHERE statement = %s"
        c.execute(stmt, statement)
        if c.fetchone() is None:
            c.execute(statement)
            c.execute("INSERT INTO schema_history VALUES(%s)", statement)
    c.close()


def query(statement, args=None):
    try:
        link = MySQLdb.connect(config['mysql']['host'],
                               config['mysql']['user'],
                               config['mysql']['password'],
                               config['mysql']['db'],
                               charset='utf8')
        link.autocommit(True)
        c = link.cursor()
        modified = c.execute(statement, args)
        if c.description:
            desc = [col[0] for col in c.description]
            result = [dict(zip(desc, data)) for data in c.fetchall()]
        else:
            result = link.insert_id()
        return modified, result
    except Exception:
        logging.getLogger('kisspush').exception("While querying MySQL "
                                                + statement)
    finally:
        c.close()


def user_create(reg_id):
    return query("""INSERT INTO user (registration_id, ctime, ltime)
                         VALUES (%s, NOW(), NOW())
        ON DUPLICATE KEY UPDATE ltime = VALUES(ltime)""",
                 reg_id)


def user_get(registration_id=None, user_id=None, alias=None):
    where = []
    args = []
    if registration_id is not None:
        where.append("registration_id = %s")
        args.append(registration_id)
    if user_id is not None:
        where.append("user_id = %s")
        args.append(user_id)
    if alias is not None:
        where.append("alias.alias = %s")
        args.append(alias)
    return query("""SELECT user_id, registration_id, ctime, ltime, alias.alias
                      FROM user
                 LEFT JOIN alias USING(user_id)
                     WHERE """ + ' AND '.join(where), args)


def alias_create(reg_id, alias):
    found, user = user_get(reg_id)
    if not found:
        return None
    return query("""INSERT IGNORE INTO alias (user_id, alias)
                    VALUES (%s, %s)""",
                 (user[0]['user_id'], alias))


def alias_get(reg_id):
    found, user = user_get(reg_id)
    if not found:
        return None
    return query("""SELECT alias FROM alias
                    WHERE user_id = %s""",
                 (user[0]['user_id']))


def message_create(message, to_alias):
    success, message_id = query("""INSERT INTO message (message, retry_after)
                                   VALUES (%s, NOW())""", message)
    qte, recipients = user_get(alias=to_alias)
    for recipient in recipients:
        query("""INSERT INTO recipient (message_id, user_id)
                      VALUES (%s, %s)""",
              (message_id, recipient['user_id']))
    return message_id


def messages_to_send():
    q = """SELECT message.message_id, message.message, user.registration_id
             FROM message
             JOIN recipient USING (message_id)
             JOIN user USING (user_id)
            WHERE message.status = "todo"
                  AND retry_after < NOW()"""
    count, todo = query(q)
    if count > 0:
        ids = [str(message['message_id']) for message in todo]
        query("UPDATE message SET status = 'done'"
              "WHERE message_id IN (" + ','.join(ids) + ")")
    return todo