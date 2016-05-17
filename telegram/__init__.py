# -*- encoding: utf-8 -*-
import main
import telegram_bus

import openerp
from openerp.service.server import Worker
from openerp.service.server import PreforkServer
import telebot
import openerp.tools.config as config
from openerp import SUPERUSER_ID
import traceback
import time
import os
import threading
import psutil
import pprint
from multiprocessing import Process


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
        token = '223555999:AAFJlG9UMLSlZIf9uqpHiOkilyDJrqAU5hA'
        bot = telebot.TeleBot(token, threaded=True)
        def mod_listener(messages):
            with openerp.api.Environment.manage():
                self.registry['telegram.command'].listener(self.db.cursor(), SUPERUSER_ID, messages, bot)
        bot.set_update_listener(mod_listener)
        threading.currentThread().bot = bot
        bt = BotThread(1)
        bt.bot = bot
        bt.start()

    def process_work(self):
        self.sleep()

    def get_telegram_token(self):
        # get token from config
        self.cr.execute()
        res = self.cr.fetchone()
        return res

    def __init__(self, multi):
        self.db_name = multi.db_name
        self.db = openerp.sql_db.db_connect(self.db_name)
        # self.cr = db.cursor()
        super(WorkerTelegram, self).__init__(multi)
        self.registry = openerp.registry(self.db_name)

class BotThread(threading.Thread):
    def __init__(self, interval):
        threading.Thread.__init__(self, name='tele_wdt_thread')
        self.daemon = True
        self.interval = interval
        self.bot = None

    def run(self):
        print '# Telegram bot thread started'
        self.bot.polling()


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