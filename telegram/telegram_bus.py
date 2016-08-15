# -*- coding: utf-8 -*-
import datetime
import json
import logging
import random
import select
import threading
import time

import openerp
from openerp import api, fields, models
from openerp.tools.misc import DEFAULT_SERVER_DATETIME_FORMAT

_logger = logging.getLogger(__name__)

# longpolling timeout connection
TIMEOUT = 50


def json_dump(v):
    return json.dumps(v, separators=(',', ':'))


def hashable(key):
    if isinstance(key, list):
        key = tuple(key)
    return key


class TelegramBus(models.Model):
    """
        This bus is to get messages from Odoo to OdooTelegramThread.
        Odoo sends commands to be executed to OdooTelegramThread using this bus.
        Such may occur for example if user got new message, or event, those like new CRM lead is created, and so on.
        OdooTelegramThread discovers about sent to it messages with help of TelegramDispatch, when listens according bus chanel.
    """
    _name = 'telegram.bus'

    create_date = fields.Datetime('Create date')
    channel = fields.Char('Channel')
    message = fields.Char('Message')

    @api.model
    def gc(self):
        timeout_ago = datetime.datetime.utcnow()-datetime.timedelta(seconds=TIMEOUT*2)
        domain = [('create_date', '<', timeout_ago.strftime(DEFAULT_SERVER_DATETIME_FORMAT))]
        return self.sudo().search(domain).unlink()

    @api.model
    def sendmany(self, notifications):
        channels = set()
        for channel, message in notifications:
            channels.add(channel)
            values = {
                "channel": json_dump(channel),
                "message": json_dump(message)
            }
            self.sudo().create(values)
            if random.random() < 0.01:
                self.gc()
        if channels:
            # The notifications must be commited in database because when calling `NOTIFY imbus`, some pertinent
            # threads will be awakened and will fetch the notification in the bus table, but since the transaction
            # is not commited, there will be nothing to fetch, the longpolling will return empty list of notification.
            # For some reason, this happen when `sendmany` is called more than once on the same request.
            # `self._cr.commit()` is prevented in a test environement, to allow test rollback.

            # Better solution is made in 9.0 by this commit
            # https://github.com/odoo/odoo/commit/18f3de2f19dcc211b10cc8b9f1cfd5fcdca22a9e
            # but we cannot apply, as there is no _cr.after function in 8.0
            if not openerp.tools.config['test_enable']:
                self._cr.commit()
            with openerp.sql_db.db_connect('postgres').cursor() as cr2:
                cr2.execute("notify telegram_bus, %s", (json_dump(list(channels)),))

    @api.model
    def sendone(self, channel, message):
        self.sendmany([[channel, message]])

    @api.model
    def poll(self, channels, last=0, options=None, force_status=False):
        if options is None:
            options = {}
        # first poll return the notification in the 'buffer'
        if last == 0:
            timeout_ago = datetime.datetime.utcnow()-datetime.timedelta(seconds=TIMEOUT)
            domain = [('create_date', '>', timeout_ago.strftime(DEFAULT_SERVER_DATETIME_FORMAT))]
        else:  # else returns the unread notifications
            domain = [('id', '>', last)]
        channels = [json_dump(c) for c in channels]
        domain.append(('channel', 'in', channels))
        notifications = self.sudo().search_read(domain)
        # list of notification to return
        result = []
        for notif in notifications:
            _logger.debug('notif: %s' % notif)
            result.append({
                'id': notif['id'],
                'channel': json.loads(notif['channel']),
                'message': json.loads(notif['message']),
            })

        if result or force_status:
            partner_ids = options.get('bus_presence_partner_ids')
            if partner_ids:
                partners = self.env['res.partner'].browse(partner_ids)
                result += [{
                    'id': -1,
                    'channel': (self._cr.dbname, 'bus.presence'),
                    'message': {'id': r.id, 'im_status': r.im_status}} for r in partners]
        return result


class TelegramDispatch(object):
    """
        Notifier thread. It notifies OdooTelegramThread about messages to it, sent by bus.
        Only one instance of TelegramDispatch for all databases.
    """
    def __init__(self):
        self.channels = {}

    def poll(self, dbname, channels, last, options=None, timeout=TIMEOUT):
        if options is None:
            options = {}
        if not openerp.evented:
            current = threading.current_thread()
            current._Thread__daemonic = True
            # rename the thread to avoid tests waiting for a longpolling
            current.setName("openerp.longpolling.request.%s" % current.ident)
        registry = openerp.registry(dbname)
        with registry.cursor() as cr:
            with openerp.api.Environment.manage():
                notifications = registry['telegram.bus'].poll(cr, openerp.SUPERUSER_ID, channels, last, options)
        # or wait for future ones
        if not notifications:
            event = self.Event()
            for channel in channels:
                self.channels.setdefault(hashable(channel), []).append(event)
            try:
                event.wait(timeout=timeout)
                with registry.cursor() as cr:
                    notifications = registry['telegram.bus'].poll(cr, openerp.SUPERUSER_ID, channels, last, options, force_status=True)
            except Exception:
                # timeout
                pass
        return notifications

    def loop(self):
        """ Dispatch postgres notifications to the relevant polling threads/greenlets """
        _logger.info("Bus.loop listen imbus on db postgres")
        with openerp.sql_db.db_connect('postgres').cursor() as cr:
            conn = cr._cnx
            cr.execute("listen telegram_bus")
            cr.commit();
            while True:
                if select.select([conn], [], [], TIMEOUT) == ([], [], []):
                    pass
                else:
                    conn.poll()
                    channels = []
                    while conn.notifies:
                        channels.extend(json.loads(conn.notifies.pop().payload))
                    # dispatch to local threads/greenlets
                    events = set()
                    for channel in channels:
                        events.update(self.channels.pop(hashable(channel), []))
                    for event in events:
                        event.set()

    def run(self):
        while True:
            try:
                self.loop()
            except Exception, e:
                _logger.exception("Bus.loop error, sleep and retry")
                time.sleep(TIMEOUT)

    def start(self):
        self.Event = threading.Event
        t = threading.Thread(name="%s.Bus" % __name__, target=self.run)
        t.daemon = True
        t.start()
        return self
