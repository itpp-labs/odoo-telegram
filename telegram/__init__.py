# -*- encoding: utf-8 -*-

from . import telegram
from . import telegram_bus
from . import controllers
from . import tools

from . import tools as teletools
import time
import openerp
from openerp.service.server import Worker
from openerp.service.server import PreforkServer
from telebot import TeleBot
from openerp import SUPERUSER_ID
import threading
import logging
from telebot import util

_logger = logging.getLogger(__name__)


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
        self.interval = 60*5  # 5 minutes
        self.threads_bundles = {}  # {db_name: {odoo_thread, odoo_dispatch}}
        self.odoo_dispatch = False
        self.watchdog_timeout = self.interval*2

    def process_work(self):
        # this called by run() in while self.alive cycle
        if not self.odoo_dispatch:
            self.odoo_dispatch = telegram_bus.TelegramDispatch().start()
        db_names = tools.db_list()
        for dbname in db_names:
            if self.threads_bundles.get(dbname, False):
                continue
            registry = tools.get_registry(dbname)
            if registry.get('telegram.bus', False):
                # _logger.info("telegram.bus in %s" % db_name)
                odoo_thread = OdooTelegramThread(self.odoo_dispatch, dbname, False)
                odoo_thread.start()
                self.threads_bundles[dbname] = {'odoo_thread': odoo_thread,
                                                'odoo_dispatch': self.odoo_dispatch}
        time.sleep(self.interval)


class BotPollingThread(threading.Thread):
    """
        This is father-thread for telegram bot execution-threads.
        When bot polling is started it at once spawns several child threads (num=telegram.num_telegram_threads).
        Then in __threaded_polling() it listens for events from telegram server.
        If it catches message from server it gives to manage this message to one of executors that calls telegram_listener().
        Listener do what command requires by it self or may send according command in telegram bus.
        For every database with token one bot and one bot_polling is created.
    """

    def __init__(self, bot):
        threading.Thread.__init__(self, name='BotPollingThread')
        self.daemon = True
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
        Amount of threads = telegram.num_odoo_threads + 1
    """

    def __init__(self, dispatch, dbname, bot):
        threading.Thread.__init__(self, name='OdooTelegramThread')
        self.daemon = True
        self.token = False
        self.dispatch = dispatch
        self.bot = bot
        self.bot_thread = False
        self.last = 0
        self.dbname = dbname
        self.num_odoo_threads = teletools.get_int_parameter(dbname, 'telegram.num_odoo_threads')

        self.odoo_thread_pool = util.ThreadPool(self.num_odoo_threads)

    def run(self):
        _logger.info("OdooTelegramThread started with %s threads" % self.num_odoo_threads)

        def listener(message, dbname, odoo_thread, bot):
            bus_message = message['message']
            if bus_message['action'] == 'token_changed':
                _logger.debug('token_changed')
                self.build_new_proc_bundle(dbname, odoo_thread)
            elif bus_message['action'] == 'odoo_threads_changed':
                _logger.info('odoo_threads_changed')
                self.update_odoo_threads(dbname, odoo_thread)
            elif bus_message['action'] == 'telegram_threads_changed':
                _logger.info('telegram_threads_changed')
                self.update_telegram_threads(dbname, odoo_thread)
            else:
                db = openerp.sql_db.db_connect(dbname)
                registry = tools.get_registry(dbname)
                with openerp.api.Environment.manage(), db.cursor() as cr:
                    try:
                        registry['telegram.command'].odoo_listener(cr, SUPERUSER_ID, message, self, bot)
                    except:
                        _logger.error('Error while processing Odoo message: %s' % message, exc_info=True)

        token = teletools.get_parameter(self.dbname, 'telegram.token')
        if not self.bot and tools.token_is_valid(token):
            # need to launch bot manually on database start
            _logger.debug('on boot telegram start')
            self.build_new_proc_bundle(self.dbname, self)

        while True:
            # Exeptions ?
            # ask TelegramDispatch about some messages.
            msg_list = self.dispatch.poll(self.dbname, last=self.last)
            for msg in msg_list:
                if msg['id'] > self.last:
                    self.last = msg['id']
                    self.odoo_thread_pool.put(listener, msg, self.dbname, self, self.bot)
                    if self.odoo_thread_pool.exception_event.wait(0):
                        self.odoo_thread_pool.raise_exceptions()

    def build_new_proc_bundle(self, dbname, odoo_thread):
        def listener(messages):
            db = openerp.sql_db.db_connect(dbname)
            registry = teletools.get_registry(dbname)
            with openerp.api.Environment.manage(), db.cursor() as cr:
                try:
                    registry['telegram.command'].telegram_listener(cr, SUPERUSER_ID, messages, bot)
                except:
                    _logger.error('Error while processing Telegram messages: %s' % messages, exc_info=True)

        token = teletools.get_parameter(dbname, 'telegram.token')
        _logger.debug(token)
        if teletools.token_is_valid(token):
            res = self.get_bundle_action(dbname, odoo_thread)
            if res == 'complete':
                _logger.info("Database %s just obtained new token or on-boot launch.", dbname)
                num_telegram_threads = teletools.get_int_parameter(dbname, 'telegram.num_telegram_threads')
                bot = TeleBotMod(token, threaded=True, num_threads=num_telegram_threads)
                bot.num_telegram_threads = num_telegram_threads
                bot.set_update_listener(listener)
                bot.dbname = dbname
                bot.add_callback_query_handler({'function': lambda call: self.callback_query_handler(call, bot), 'filters': {}})
                bot_thread = BotPollingThread(bot)
                bot_thread.start()
                odoo_thread.token = token
                odoo_thread.bot = bot
                odoo_thread.bot_thread = bot_thread

    @staticmethod
    def get_bundle_action(dbname, odoo_thread):
        # update - means token was updated
        # complete - means TelegramDispatch and OdooTelegramThread already created and we just need complete threads_bundles with bot and BotPollingThread
        # new - means there is no even TelegramDispatch and OdooTelegramThread
        if odoo_thread.bot:
            return 'update'
        elif dbname:
            return 'complete'
        return 'new'

    @staticmethod
    def update_odoo_threads(dbname, odoo_thread):
        new_num_threads = teletools.get_int_parameter(dbname, 'telegram.num_odoo_threads')
        diff = new_num_threads - odoo_thread.num_odoo_threads
        odoo_thread.num_odoo_threads += diff
        OdooTelegramThread._update_threads(diff, 'Odoo', odoo_thread.odoo_thread_pool)

    @staticmethod
    def update_telegram_threads(dbname, odoo_thread):
        new_num_threads = teletools.get_int_parameter(dbname, 'telegram.num_telegram_threads')
        diff = new_num_threads - odoo_thread.bot.num_telegram_threads
        odoo_thread.bot.num_telegram_threads += diff
        OdooTelegramThread._update_threads(diff, 'Telegram', odoo_thread.bot.worker_pool)

    @staticmethod
    def _update_threads(diff, proc_name, wp):
        if diff > 0:
            # add new threads
            wp.workers += [util.WorkerThread(wp.on_exception, wp.tasks) for _ in range(diff)]
            _logger.info("%s workers increased and now its amount = %s" % (proc_name, teletools.running_workers_num(wp.workers)))
        elif diff < 0:
            # decrease threads
            cnt = 0
            for i in range(len(wp.workers)):
                if wp.workers[i]._running:
                    wp.workers[i].stop()
                    _logger.info('%s worker [id=%s] stopped' % (proc_name, wp.workers[i].ident))
                    cnt += 1
                    if cnt >= -diff:
                        break
            cnt = 0
            for i in range(len(wp.workers)):
                if not wp.workers[i]._running:
                    _logger.info('%s worker [id=%s] joined' % (proc_name, wp.workers[i].ident))
                    wp.workers[i].join()
                    cnt += 1
                    if cnt >= -diff:
                        break
            _logger.info("%s workers decreased and now its amount = %s" % (proc_name, teletools.running_workers_num(wp.workers)))

    @staticmethod
    def callback_query_handler(call, bot):
        # Если сообщение из чата с ботом
        _logger.debug("callback_inline msg: %s" % call.message)
        if call.message:
            if call.data:
                _logger.debug("callback_inline data: %s" % call.data)
                _logger.debug("callback_inline call: %s" % call)
                command_name = call.data.split('_')[0]
                db = openerp.sql_db.db_connect(bot.dbname)
                registry = teletools.get_registry(bot.dbname)
                with openerp.api.Environment.manage(), db.cursor() as cr:
                    command_id = registry['telegram.command'].search(cr, SUPERUSER_ID,
                                                                     [('name', '=', '/' + command_name)],
                                                                     limit=1)
                    command = registry['telegram.command'].browse(cr, SUPERUSER_ID, command_id)
                    if not command:
                        _logger.error('Command %s not found.' % command_name, exc_info=True)
                        return
                    _logger.debug("callback_inline command: %s" % command)
                    tsession = registry['telegram.session'].get_session(cr, SUPERUSER_ID,
                                                                        call.message.chat.id)
                    _logger.debug("callback_inline tsession: %s" % tsession)
                    response = command.get_response({'callback_data': call.data}, tsession)
                    # bot.cache.set_value(command, response, tsession)
                    registry['telegram.command'].send(cr, SUPERUSER_ID, bot, response, tsession)

        # Если сообщение из инлайн-режима
        elif call.inline_message_id:
            if call.data:
                pass


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
