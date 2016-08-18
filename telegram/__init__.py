# -*- encoding: utf-8 -*-

from openerp import models
import telegram
import telegram_bus
import controllers
import random
import datetime
import dateutil
import time
import sys
import openerp
from openerp.service.server import Worker
from openerp.service.server import PreforkServer
from openerp.tools.safe_eval import safe_eval
from openerp.tools.translate import _
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

_logger = logging.getLogger(__name__)


def get_registry(db_name):
    openerp.modules.registry.RegistryManager.check_registry_signaling(db_name)
    registry = openerp.registry(db_name)
    return registry


def get_parameter(db_name, key):
    db = openerp.sql_db.db_connect(db_name)
    registry = get_registry(db_name)
    with openerp.api.Environment.manage(), db.cursor() as cr:
        return registry['ir.config_parameter'].get_param(cr, SUPERUSER_ID, key)
#
#    result = None
#    with openerp.api.Environment.manage(), db.cursor() as cr:
#        res = registry['ir.config_parameter'].search(cr, SUPERUSER_ID, [('key', '=', key)])
#        if len(res) == 1:
#            val = registry['ir.config_parameter'].browse(cr, SUPERUSER_ID, res[0])
#            return val.value
#    return None


def running_workers_num(workers):
    res = 0
    for r in workers:
        if r._running:
            res += 1
    return res


def _db_list():
    if config['db_name']:
        db_names = config['db_name'].split(',')
    else:
        db_names = openerp.service.db.list_dbs(True)
    return db_names


def telegram_worker():
    # monkey patch
    old_process_spawn = PreforkServer.process_spawn

    def process_spawn(self):
        old_process_spawn(self)
        while len(self.workers_telegram) < self.telegram_population:
            # only 1 telegram process we create.
            self.worker_spawn(WorkerTelegram, self.workers_telegram)

    PreforkServer.process_spawn = process_spawn
    old_init = PreforkServer.__init__

    def __init__(self, app):
        old_init(self, app)
        self.workers_telegram = {}
        self.telegram_population = 1
    PreforkServer.__init__ = __init__


class WorkerTelegram(Worker):
    """
        This is main singleton process for all other telegram purposes.
        It creates one TelegramDispatch (events bus), one OdooTelegramThread, several TeleBotMod and BotPollingThread threads.
    """
    def __init__(self, multi):
        super(WorkerTelegram, self).__init__(multi)
        self.interval = 10
        self.threads_bundles_list = []  # token, bot, odoo_thread, odoo_dispatch
        self.singles_ran = False  # indicates one instance of odoo_dispatcher and odoo_thread exists
        self.odoo_thread = False
        self.odoo_dispatch = False

    def process_work(self):
        # this called by run() in while self.alive cycle
        def listener(messages):
            db = openerp.sql_db.db_connect(bot.db_name)
            registry = get_registry(bot.db_name)
            with openerp.api.Environment.manage(), db.cursor() as cr:
                try:
                    registry['telegram.command'].telegram_listener(cr, SUPERUSER_ID, messages, bot)
                except:
                    _logger.error('Error while proccessing Telegram messages: %s' % messages, exc_info=True)

        db_names = _db_list()
        if not self.singles_ran:
            self.odoo_dispatch = telegram_bus.TelegramDispatch().start()
            self.odoo_thread = OdooTelegramThread(self.interval, self.odoo_dispatch, self.threads_bundles_list)
            self.odoo_thread.start()
            self.singles_ran = True
        for db_name in db_names:
            token = get_parameter(db_name, 'telegram.token')
            if token and len(token) > 10 and self.need_new_bundle(token):
                _logger.info("Database %s has token.", db_name)
                num_telegram_threads = int(get_parameter(db_name, 'telegram.telegram_threads'))
                bot = TeleBotMod(token, threaded=True, num_threads=num_telegram_threads)
                bot.telegram_threads = num_telegram_threads
                bot.set_update_listener(listener)
                bot.db_name = db_name  # needs in telegram_listener()
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
        if random.random() < 0.01:
            self.manage_threads()  # increase or decrease number of threads

    def need_new_bundle(self, token):
        for bundle in self.threads_bundles_list:
            if bundle['token'] == token:
                return False
        return True

    def manage_threads(self):
        for bundle in self.threads_bundles_list:
            bot = bundle['bot']
            wp = bot.worker_pool
            new_num_threads = int(get_parameter(bot.db_name, 'telegram.telegram_threads'))
            diff = new_num_threads - bot.telegram_threads
            if new_num_threads > bot.telegram_threads:
                # add new threads
                wp.workers += [util.WorkerThread(wp.on_exception, wp.tasks) for _ in range(diff)]
                bot.telegram_threads += diff
                _logger.info("Telegram workers increased and now its amount = %s" % running_workers_num(wp.workers))
            elif new_num_threads < bot.telegram_threads:
                # decrease threads
                cnt = 0
                for i in range(len(wp.workers)):
                    if wp.workers[i]._running:
                        wp.workers[i].stop()
                        _logger.info('Telegram worker stop')
                        cnt += 1
                        if cnt >= -diff:
                            break
                cnt = 0
                for i in range(len(wp.workers)):
                    if not wp.workers[i]._running:
                        wp.workers[i].join()
                        _logger.info('Telegram worker join')
                        cnt += 1
                        if cnt >= -diff:
                            break
                bot.telegram_threads += diff
                _logger.info("Telegram workers decreased and now its amount = %s" % running_workers_num(wp.workers))


class BotPollingThread(threading.Thread):
    """
        This is father-thread for telegram bot execution-threads.
        When bot polling is started it at once spawns several child threads (num=telegram.telegram_threads).
        Then in __threaded_polling() it listens for events from telegram server.
        If it catches message from server it gives to manage this message to one of executors that calls telegram_listener().
        Listener do what command requires by it self or may send according command in telegram bus.
        For every database with token one bot and one bot_polling is created.
    """
    def __init__(self, interval, bot):
        threading.Thread.__init__(self, name='BotPollingThread')
        self.daemon = True
        self.interval = interval
        self.bot = bot

    def run(self):
        _logger.info("BotPollingThread started.")
        self.bot.polling()


class OdooTelegramThread(threading.Thread):
    """
        This is father-thread for odoo events execution-threads.
        When it started it at once spawns several execution threads.
        Then listens for some odoo events, pushed in telegram bus.
        If some event happened OdooTelegramThread find out about it by dispatch and gives to manage this event to one of executors.
        Executor do what needed in odoo_listener() method.
        Spawned threads are in odoo_thread_pool.
        Amount of threads = telegram.odoo_threads + 1
    """
    def __init__(self, interval, dispatch, threads_bundles_list):
        threading.Thread.__init__(self, name='OdooTelegramThread')
        self.daemon = True
        self.interval = interval
        self.dispatch = dispatch
        self.threads_bundles_list = threads_bundles_list
        self.last = 0
        self.odoo_threads = self.get_num_of_children()
        self.odoo_thread_pool = util.ThreadPool(self.odoo_threads)

    def run(self):
        _logger.info("OdooTelegramThread started with %s threads" % self.odoo_threads)

        def listener(message, bot):
            db = openerp.sql_db.db_connect(bot.db_name)
            registry = get_registry(bot.db_name)
            with openerp.api.Environment.manage(), db.cursor() as cr:
                try:
                    registry['telegram.command'].odoo_listener(cr, SUPERUSER_ID, message, bot)
                except:
                    _logger.error('Error while proccessing Odoo message: %s' % message, exc_info=True)

        while True:
            # Exeptions ?
            db_names = _db_list()
            for db_name in db_names:  # successively check notifications in all bases with token
                token = get_parameter(db_name, 'telegram.token')
                if not token:
                    continue
                # ask TelegramDispatch about some messages.
                msg_list = self.dispatch.poll(dbname=db_name, channels=['telegram_channel'], last=self.last)
                for msg in msg_list:
                    if msg['id'] > self.last:
                        self.last = msg['id']
                    ls = [s for s in self.threads_bundles_list if s['token'] == token]
                    if len(ls) == 1:
                        self.odoo_thread_pool.put(listener, msg, ls[0]['bot'])
                        if self.odoo_thread_pool.exception_event.wait(0):
                            self.odoo_thread_pool.raise_exceptions()
                    elif len(ls) > 1:
                        raise ValidationError(_('Token is not unique'))
                    elif len(ls) == 0:
                        raise ValidationError(_('Unregistered token'))
            self.manage_threads()

    @staticmethod
    def get_num_of_children():
        db_names = _db_list()
        n = 1  # its minimum
        for db_name in db_names:
            num = get_parameter(db_name, 'telegram.odoo_threads')
            if num:
                n += int(num)
        return n

    def manage_threads(self):
            new_num_threads = self.get_num_of_children()
            diff = new_num_threads - self.odoo_threads
            wp = self.odoo_thread_pool
            if new_num_threads > self.odoo_threads:
                # add new threads
                wp.workers += [util.WorkerThread(wp.on_exception, wp.tasks) for _ in range(diff)]
                self.odoo_threads += diff
                _logger.info("Odoo workers increased and now its amount = %s" % running_workers_num(wp.workers))
            elif new_num_threads < self.odoo_threads:
                # decrease threads
                cnt = 0
                for i in range(len(wp.workers)):
                    if wp.workers[i]._running:
                        wp.workers[i].stop()
                        _logger.info('Odoo worker stop')
                        cnt += 1
                        if cnt >= -diff:
                            break
                cnt = 0
                for i in range(len(wp.workers)):
                    if not wp.workers[i]._running:
                        wp.workers[i].join()
                        _logger.info('Odoo worker join')
                        cnt += 1
                        if cnt >= -diff:
                            break
                self.odoo_threads += diff
                _logger.info("Odoo workers decreased and now its amount = %s" % running_workers_num(wp.workers))


class TeleBotMod(TeleBot, object):
    """
        Little bit modified TeleBot. Just to control amount of children threads to be created.
    """
    def __init__(self, token, threaded=True, skip_pending=False, num_threads=2):
        super(TeleBotMod, self).__init__(token, threaded=False, skip_pending=skip_pending)
        self.worker_pool = util.ThreadPool(num_threads)
        self.cache = CommandCache()
        _logger.info("TeleBot started with %s threads" % num_threads)


class CommandCache(object):
    """
        Cache structure:
        {
          <command_id>: {
             <user_id1>: <response1>
             <user_id2>: <response2>
          }
        }
    """
    def __init__(self):
        self._vals = {}

    def set_value(self, command, response, tsession=None):
        if command.type != 'cacheable':
            return

        user_id = 0
        if not command.universal:
            user_id = tsession.user_id.id

        if command.id not in self._vals:
            self._vals[command.id] = {}
        self._vals[command.id][user_id] = response

    def get_value(self, command, tsession):
        user_id = 0
        if not command.universal:
            user_id = tsession.user_id.id

        if command.id not in self._vals:
            return False
        return self._vals[command.id].get(user_id)



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
