# -*- encoding: utf-8 -*-

from openerp import models
from . import telegram
from . import telegram_bus
from . import controllers
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
from telebot import apihelper, types, util

_logger = logging.getLogger('# ' + __name__)


def get_registry(db_name):
    openerp.modules.registry.RegistryManager.check_registry_signaling(db_name)
    registry = openerp.registry(db_name)
    return registry


def need_new_bundle(threads_bundles_list, db_name):
    for bundle in threads_bundles_list:
        if bundle['db_name'] == db_name:
            return False
    return True


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
        self.threads_bundles_list = []  # db_name, token, bot, odoo_thread, odoo_dispatch
        self.singles_ran = False  # indicates one instance of odoo_dispatcher and odoo_thread exists
        self.odoo_thread = False
        self.odoo_dispatch = False
        self.manager = False

    def process_work(self):
        # this called by run() in while self.alive cycle
        db_names = _db_list()
        for db_name in db_names:
            registry = get_registry(db_name)
            if registry.get('telegram.bus', False):
                # _logger.info("telegram.bus in %s" % db_name)
                if not need_new_bundle(self.threads_bundles_list, db_name):
                    continue
                _logger.info("telegram.bus Need to create new bundle for %s" % db_name)
                self.odoo_dispatch = telegram_bus.TelegramDispatch().start()
                self.odoo_thread = OdooTelegramThread(self.interval, self.odoo_dispatch, self.threads_bundles_list)
                self.manager = telegram.TelegramManager(self.odoo_thread, self.threads_bundles_list)
                self.odoo_thread.start()
                vals = {'db_name': db_name,
                        'odoo_thread': self.odoo_thread,
                        'bot': False,
                        'odoo_dispatch': self.odoo_dispatch}
                self.threads_bundles_list.append(vals)
        time.sleep(self.interval / 2)

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


