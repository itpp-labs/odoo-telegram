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
        bot_thread = BotPollingThread(1, bot)
        odoo_thread = OdooThread(1, bot, dispatch,  self.db, self.db_name)
        bot_thread.start()
        odoo_thread.start()

    def process_work(self):
        time.sleep(2)

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


class BotPollingThread(threading.Thread):
    def __init__(self, interval, bot):
        threading.Thread.__init__(self, name='tele_wdt_thread')
        self.daemon = True
        self.interval = interval
        self.bot = bot

    def run(self):
        print '# Telegram bot thread started'
        self.bot.polling()


class OdooThread(threading.Thread):
    def __init__(self, interval, bot, dispatch, db, db_name):
        threading.Thread.__init__(self, name='tele_wdt_thread')
        self.daemon = True
        self.interval = interval
        self.bot = bot
        self.db = db
        self.db_name = db_name
        self.dispatch = dispatch
        self.worker_pool = util.ThreadPool()
        self.registry = openerp.registry(self.db_name)
        self.last = 0
        self.proceeded_messages = []

    def run(self):

        def listener(message, bot):
            with openerp.api.Environment.manage(), self.db.cursor() as cr:
                self.registry['telegram.command'].odoo_listener(message, bot)

        while True:
            res = self.dispatch.poll(dbname=self.db_name, channels=['telegram_channel'], last=self.last)
            for r in res:
                if r not in self.proceeded_messages:
                    self.proceeded_messages.append(r)
                    if r['id'] > self.last:
                        self.last = r['id']
                    self.worker_pool.put(listener, r, self.bot)
                    if self.worker_pool.exception_event.wait(0):
                        self.worker_pool.raise_exceptions()
                else:
                    print '# skipped'


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