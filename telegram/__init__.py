# -*- encoding: utf-8 -*-
import telegram
import telegram_bus
import controllers

import openerp
from openerp.service.server import Worker
from openerp.service.server import PreforkServer
import telebot
import telebot.util as util
import openerp.tools.config as config
from openerp import SUPERUSER_ID
import threading
import logging
import time
from telebot import apihelper, types, util

logger = logging.getLogger('Telegram')
# from openerp.addons.telegram import dispatch

def telegram_worker():
    old_process_spawn = PreforkServer.process_spawn

    def process_spawn(self):
        old_process_spawn(self)
        db_names = _db_list(self)
        for db_name in db_names:
            self.db_name = db_name

            while len(self.workers_telegram) < self.telegram_population:
                worker = self.worker_spawn(WorkerTelegram, self.workers_telegram)
                worker.db_name = db_name

    PreforkServer.process_spawn = process_spawn
    old_init = PreforkServer.__init__

    def __init__(self, app):
        old_init(self, app)
        self.workers_telegram = {}
        self.telegram_population = 1
    PreforkServer.__init__ = __init__


class WorkerTelegram(Worker):
    def start(self):
        # token = self.get_telegram_token()
        # token = '223555999:AAFJlG9UMLSlZIf9uqpHiOkilyDJrqAU5hA'
        with openerp.api.Environment.manage(), self.db.cursor() as cr:
            token = self.get_telegram_token(cr)
            bot = telebot.TeleBot(token, threaded=True)
        def listener(messages):
            with openerp.api.Environment.manage(), self.db.cursor() as cr:
                self.registry['telegram.command'].telegram_listener(cr, SUPERUSER_ID, messages, bot)
        bot.set_update_listener(listener)
        dispatch = telegram_bus.TelegramImDispatch().start()
        threading.currentThread().bot = bot
        bot_thread = BotThread(1, bot)
        odoo_thread = OdooThread(1, bot, dispatch,  self.db_name)
        bot_thread.start()
        odoo_thread.start()

    def process_work(self):
        self.sleep()

    def get_telegram_token(self, cr):
        icp = self.registry['ir.config_parameter']
        res = icp.get_param(cr, SUPERUSER_ID, 'telegram.token')
        return res

    def __init__(self, multi):
        self.db_name = multi.db_name
        self.db = openerp.sql_db.db_connect(self.db_name)
        # self.cr = db.cursor()
        super(WorkerTelegram, self).__init__(multi)
        self.registry = openerp.registry(self.db_name)


class BotThread(threading.Thread):
    def __init__(self, interval, bot):
        threading.Thread.__init__(self, name='tele_wdt_thread')
        self.daemon = True
        self.interval = interval
        self.bot = bot

    def run(self):
        print '# Telegram bot thread started'
        self.bot.polling()


class OdooThread:
    def __init__(self, interval, bot, dispatch, db_name):
        threading.Thread.__init__(self, name='tele_wdt_thread')
        self.daemon = True
        self.interval = interval
        self.bot = bot
        self.db_name = db_name
        self.dispatch = dispatch
        self.worker_pool = util.ThreadPool()
        self.__stop_polling = threading.Event()

    def __threaded_polling(self, none_stop=False, interval=0, timeout=3):
        logger.info('Started polling.')
        self.__stop_polling.clear()
        error_interval = .25

        polling_thread = util.WorkerThread(name="OdooTelePollingThread")
        or_event = util.OrEvent(
            polling_thread.done_event,
            polling_thread.exception_event,
            self.worker_pool.exception_event
        )

        while not self.__stop_polling.wait(interval):
            or_event.clear()
            try:
                polling_thread.put(self.__retrieve_updates, timeout)

                or_event.wait()  # wait for polling thread finish, polling thread error or thread pool error

                polling_thread.raise_exceptions()
                self.worker_pool.raise_exceptions()

                error_interval = .25
            except apihelper.ApiException as e:
                logger.error(e)
                if not none_stop:
                    self.__stop_polling.set()
                    logger.info("Exception occurred. Stopping.")
                else:
                    polling_thread.clear_exceptions()
                    self.worker_pool.clear_exceptions()
                    logger.info("Waiting for {0} seconds until retry".format(error_interval))
                    time.sleep(error_interval)
                    error_interval *= 2
            except KeyboardInterrupt:
                logger.info("KeyboardInterrupt received.")
                self.__stop_polling.set()
                polling_thread.stop()
                break

        logger.info('Stopped polling.')

    def __exec_task(self, task, *args, **kwargs):
        self.worker_pool.put(task, *args, **kwargs)

    def __retrieve_updates(self, timeout=20):
        """
        Retrieves any updates from the Telegram API.
        Registered listeners and applicable message handlers will be notified when a new message arrives.
        :raises ApiException when a call has failed.
        """
        if self.skip_pending:
            logger.debug('Skipped {0} pending messages'.format(self.__skip_updates()))
            self.skip_pending = False
        updates = self.get_updates(offset=(self.last_update_id + 1), timeout=timeout)
        self.process_new_updates(updates)


    def process_new_updates(self, updates):
        new_messages = []
        new_inline_querys = []
        new_chosen_inline_results = []
        new_callback_querys = []
        for update in updates:
            if update.update_id > self.last_update_id:
                self.last_update_id = update.update_id
            if update.message:
                new_messages.append(update.message)
            if update.inline_query:
                new_inline_querys.append(update.inline_query)
            if update.chosen_inline_result:
                new_chosen_inline_results.append(update.chosen_inline_result)
            if update.callback_query:
                new_callback_querys.append(update.callback_query)
        logger.debug('Received {0} new updates'.format(len(updates)))
        if len(new_messages) > 0:
            self.process_new_messages(new_messages)
        if len(new_inline_querys) > 0:
            self.process_new_inline_query(new_inline_querys)
        if len(new_chosen_inline_results) > 0:
            self.process_new_chosen_inline_query(new_chosen_inline_results)
        if len(new_callback_querys) > 0:
            self.process_new_callback_query(new_callback_querys)


    def process_new_messages(self, new_messages):
        self._append_pre_next_step_handler()
        self.__notify_update(new_messages)
        self._notify_command_handlers(self.message_handlers, new_messages)
        self._notify_message_subscribers(new_messages)
        self._notify_message_next_handler(new_messages)


def _db_list(self):
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