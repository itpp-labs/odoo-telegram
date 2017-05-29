# -*- coding: utf-8 -*-

# local imports, that can be unused:
from . import telegram
from . import telegram_bus
from . import controllers
from . import tools
from . import tools as teletools

# usual imports
import time
import openerp
from openerp.service.server import Worker
from openerp.service.server import PreforkServer

from openerp import SUPERUSER_ID
import threading
import logging

_logger = logging.getLogger(__name__)

try:
    from telebot import TeleBot, util
except (ImportError, IOError) as err:
    # cannot import TeleBot, so create dummy class 
    class TeleBot(object):
        pass
    _logger.debug(err)


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

    def odoo_execute(self, dbname, model, method, args, kwargs=None):
        kwargs = kwargs or {}
        db = openerp.sql_db.db_connect(dbname)
        registry = tools.get_registry(dbname)
        with openerp.api.Environment.manage(), db.cursor() as cr:
            try:
                _logger.debug('%s: %s %s', method, args, kwargs)
                getattr(registry[model], method)(cr, SUPERUSER_ID, *args, **kwargs)
            except:
                _logger.error('Error while executing method=%s, args=%s, kwargs=%s',
                              method, args, kwargs, exc_info=True)

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
                self.odoo_execute(
                    dbname,
                    'telegram.command',
                    'odoo_listener',
                    (message, bot))

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
        token = teletools.get_parameter(dbname, 'telegram.token')
        _logger.debug(token)
        if teletools.token_is_valid(token):
            if not odoo_thread.bot:
                _logger.info("Database %s just obtained new token or on-boot launch.", dbname)
                num_telegram_threads = teletools.get_int_parameter(dbname, 'telegram.num_telegram_threads')
                bot = TeleBotMod(token, threaded=True, num_threads=num_telegram_threads)
                bot.num_telegram_threads = num_telegram_threads
                bot.set_update_listener(
                    lambda messages:
                    self.odoo_execute(
                        dbname,
                        'telegram.command',
                        'telegram_listener_message',
                        (messages, bot))
                )
                bot.dbname = dbname
                bot.add_callback_query_handler({
                    'function': lambda call:
                    self.odoo_execute(
                        dbname,
                        'telegram.command',
                        'telegram_listener_callback_query',
                        (call, bot)
                    ),
                    'filters': {}})
                bot_thread = BotPollingThread(bot)
                bot_thread.start()
                odoo_thread.token = token
                odoo_thread.bot = bot
                odoo_thread.bot_thread = bot_thread

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
