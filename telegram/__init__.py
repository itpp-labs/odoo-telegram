# -*- encoding: utf-8 -*-
import telegram
import telegram_bus
import controllers

import openerp
from openerp.service.server import Worker
from openerp.service.server import PreforkServer
import telebot
from telebot import TeleBot
import telebot.util as util
import openerp.tools.config as config
from openerp import SUPERUSER_ID
from openerp.exceptions import ValidationError
import threading
import logging
import time
from telebot import apihelper, types, util

_logger = logging.getLogger('Telegram')
# from openerp.addons.telegram import dispatch


def telegram_worker():
    # monkey patch
    old_process_spawn = PreforkServer.process_spawn

    def process_spawn(self):
        old_process_spawn(self)
        while len(self.workers_telegram) < self.telegram_population:
            # only 1 telegram process we create.
            worker = self.worker_spawn(WorkerTelegram, self.workers_telegram)

    PreforkServer.process_spawn = process_spawn
    old_init = PreforkServer.__init__

    def __init__(self, app):
        old_init(self, app)
        self.workers_telegram = {}
        self.telegram_population = 1
    PreforkServer.__init__ = __init__


class WorkerTelegram(Worker):
    def __init__(self, multi):
        super(WorkerTelegram, self).__init__(multi)
        self.interval = 10
        self.threads_bundles_list = []  # token, bot, odoo, dispatcher
        self.singles_ran = False  # for one instance of odoo_dispatcher and odoo_thread
        self.odoo_thread = False
        self.odoo_dispatch = False

    def process_work(self):
        # this called by run() in while self.alive cycle
        # only one process. threads as many as bases
        # dynamically add new threads bundle (bot, odoo, dispatcher) for each base
        # that also needed for runbot
        db_names = _db_list()
        if not self.singles_ran:
            self.odoo_dispatch = telegram_bus.TelegramDispatch().start()
            self.odoo_thread = OdooThread(self.interval, self.odoo_dispatch, self.threads_bundles_list)
            self.odoo_thread.start()
            self.singles_ran = True
        for db_name in db_names:
            token = get_parameter(db_name, 'telegram.token')
            if token != 'null' and self.need_new_bundle(token):
                num_threads = get_parameter(db_name, 'telegram.telegram_threads')
                bot = TeleBotMod(token, threaded=True, num_threads=num_threads)
                _logger.info("Token %s used for bot running.", token)
            else:
                _logger.info("Database %s has no token.", db_name)
                continue

            def listener(messages):
                db = openerp.sql_db.db_connect(bot.db_name)
                registry = openerp.registry(bot.db_name)
                with openerp.api.Environment.manage(), db.cursor() as cr:
                    registry['telegram.command'].telegram_listener(cr, SUPERUSER_ID, messages, bot)
            bot.set_update_listener(listener)
            bot.db_name = db_name  # need in telegram_listener()
            threading.currentThread().bot = bot
            bot_thread = BotPollingThread(self.interval, bot)
            bot_thread.start()
            vals = {'token': token,
                    'bot': bot,
                    'bot_thread': bot_thread,
                    'odoo_thread': self.odoo_thread,
                    'odoo_dispatch': self.odoo_dispatch}
            self.threads_bundles_list.append(vals)
            time.sleep(self.interval / 2)

    def need_new_bundle(self, token):
        for bundle in self.threads_bundles_list:
            if bundle['token'] == token:
                return False
        return True


class BotPollingThread(threading.Thread):
    def __init__(self, interval, bot):
        threading.Thread.__init__(self, name='tele_wdt_thread')
        self.daemon = True
        self.interval = interval
        self.bot = bot

    def run(self):
        _logger.info("BotPollingThread started.")
        self.bot.polling()


class OdooThread(threading.Thread):
    def __init__(self, interval, dispatch, threads_bundles_list):
        threading.Thread.__init__(self, name='tele_wdt_thread')
        self.daemon = True
        self.interval = interval
        self.dispatch = dispatch
        self.threads_bundles_list = threads_bundles_list
        self.last = 0
        self.proceeded_messages = []
        self._do_init()

    def _do_init(self):
        # some stuff need to be reinitialised some times. It placed here.
        num_of_child_threads = self.get_num_of_children()
        # not sure here. whats going to be if to recall ThreadPool init. Old workers killed ?
        # TODO need to modify ThreadPool to be able inc/dec number of threads.
        self.odoo_thread_pool = util.ThreadPool(num_of_child_threads)

    def run(self):
        _logger.info("OdooThread started.")
        def listener(message, bot):
            db = openerp.sql_db.db_connect(bot.db_name)
            registry = openerp.registry(bot.db_name)
            with openerp.api.Environment.manage(), db.cursor() as cr:
                registry['telegram.command'].odoo_listener(message, bot)
        while True:
            # Exeptions ?
            db_names = _db_list()
            for db_name in db_names:  # successively check notifications in bases
                token = get_parameter(db_name, 'telegram.token')
                if not token:
                    continue
                res = self.dispatch.poll(dbname=db_name, channels=['telegram_channel'], last=self.last)
                for r in res:
                    if r not in self.proceeded_messages:
                        self.proceeded_messages.append(r)
                        if r['id'] > self.last:
                            self.last = r['id']
                        ls = [r for r in self.threads_bundles_list if r['token'] == token]
                        if len(ls) == 1:
                            self.odoo_thread_pool.put(listener, r, ls[0]['bot'])
                            if self.odoo_thread_pool.exception_event.wait(0):
                                self.odoo_thread_pool.raise_exceptions()
                        elif len(ls) > 1:
                            raise ValidationError('Token is not unique')
                        elif len(ls) == 0:
                            raise ValidationError('Unregistered token')
            # self._do_init()  doubtfully.

    def get_num_of_children(self):
        db_names = _db_list()
        n = 1  # its minimum
        for db_name in db_names:
            num = get_parameter(db_name, 'telegram.odoo_threads')
            if num:
                n += int(num)
        return n


class TeleBotMod(TeleBot, object):
    def __init__(self, token, threaded=True, skip_pending=False, num_threads=2):
        super(TeleBotMod, self).__init__(token, threaded=False, skip_pending=skip_pending)
        if self.threaded:
            self.worker_pool = util.ThreadPool(num_threads)


def get_parameter(db_name, key):
    db = openerp.sql_db.db_connect(db_name)
    registry = openerp.registry(db_name)
    result = None
    with openerp.api.Environment.manage(), db.cursor() as cr:
        res = registry['ir.config_parameter'].search(cr, SUPERUSER_ID, [('key', '=', key)])
        if len(res) == 1:
            val = registry['ir.config_parameter'].browse(cr, SUPERUSER_ID, res[0])
            result = val.value
        elif len(res) > 1:
            raise ValidationError('Multiple values for %s' % key)
        elif len(res) < 1:
            print '# WARNING. No value for key:', key
            return None
    return result


def _db_list():
    if config['db_name']:
        db_names = config['db_name'].split(',')
    else:
        db_names = openerp.service.db.list_dbs(True)
    return db_names


def dump(obj):
  for attr in dir(obj):
    print "obj.%s = %s" % (attr, getattr(obj, attr))


def dumpclean(obj):
    if type(obj) == dict:
        for k, v in obj.items():
            if hasattr(v, '__iter__'):
                print k
                dumpclean(v)
            else:
                print '%s : %s' % (k, v)
    elif type(obj) == list:
        for v in obj:
            if hasattr(v, '__iter__'):
                dumpclean(v)
            else:
                print v
    else:
        print obj