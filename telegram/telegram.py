# -*- coding:utf-8 -*-

import openerp
from openerp import api, models, fields
import openerp.addons.auth_signup.res_users as res_users
from openerp.http import request
from openerp import SUPERUSER_ID
from openerp.addons.base.ir import ir_qweb
from openerp.exceptions import ValidationError
from openerp.tools.safe_eval import safe_eval
import datetime
import dateutil
import time
import logging
import telebot
import sys
from lxml import etree
from openerp.addons.base.ir.ir_qweb import QWebContext

_logger = logging.getLogger('# Telegram')
# telebot.logger.setLevel(logging.DEBUG)
SAFE_EVAL_BASE = {
    'datetime': datetime,
    'dateutil': dateutil,
    'time': time,
}


class TelegramCommand(models.Model):
    """
        Model represents Telegram commands that may be proceeded.
        Other modules can add new commands by adding some records of telegram.command model.
        Command must have:
          - python_code to execute;
          - response_code to handle odoo response on executed python_code as optional;
          - and web controllers if it is needed.
    """
    _name = "telegram.command"

    name = fields.Char()
    python_code = fields.Char()
    response_code = fields.Char()
    group_ids = fields.One2many('res.groups', 'telegram_command_id')
    response_template = fields.Char()
    notify_template = fields.Char()

    @api.model
    def telegram_listener(self, messages, bot):
        # python_code execution method
        for m in messages:  # messages from telegram server
            res = self.env['telegram.command'].search([('name', '=', m.text)], limit=1)
            if len(res) == 1:
                locals_dict = {'self': self, 'bot': bot, 'm': m,
                               'TelegramUser': TelegramUser,
                               'get_parameter': get_parameter}
                safe_eval(res[0].python_code, SAFE_EVAL_BASE, locals_dict, mode="exec", nocopy=True)
                self.render_and_send(bot, res[0].response_template, locals_dict, telegram_message=m)
            elif len(res) > 1:
                raise ValidationError('Multiple values for %s' % res)
            else:
                bot.send_message(m.chat.id, 'No such command: < %s > .' % m.text)

    @api.model
    def odoo_listener(self, message, bot):
        m = message['message']  # message from bus, not from telegram server.
        registry = openerp.registry(bot.db_name)
        db = openerp.sql_db.db_connect(bot.db_name)
        with openerp.api.Environment.manage(), db.cursor() as cr:
            command_id = registry['telegram.command'].search(cr, SUPERUSER_ID, [('name', '=', m['action'])])
            command = registry['telegram.command'].browse(cr, SUPERUSER_ID, command_id)
            if len(command) == 1:
                if command.response_code:
                    locals_dict = {'bot': bot, 'm': m,
                                   'TelegramUser': TelegramUser,
                                   'get_parameter': get_parameter}
                    safe_eval(command.response_code, SAFE_EVAL_BASE, locals_dict, mode="exec", nocopy=True)
                    self.render_and_send(bot, command.notify_template, locals_dict, bus_message=m)
                else:
                    pass  # No response code for this command. Response code is optional.
            elif len(command) > 1:
                raise ValidationError('Multiple values for %s' % command)

    def render_and_send(self, bot, template, locals_dict, bus_message=False, telegram_message=False):
        """Response or notify user. template - xml to render with locals_dict."""
        qweb = self.pool['ir.qweb']
        context = QWebContext(self._cr, self._uid, {})
        ctx = context.copy()
        ctx.update({'locals_dict': locals_dict})
        dom = etree.fromstring(template)
        rend = qweb.render_node(dom, ctx)
        _logger.info(rend)
        if bus_message:
            chat_id = bus_message['chat_id']
        elif telegram_message:
            chat_id = telegram_message.chat.id
        else:
            return
        bot.send_message(chat_id, rend, parse_mode='HTML')


class TelegramUser(models.TransientModel):
    _name = "telegram.user"

    chat_id = fields.Char()  # Primary key
    token = fields.Char()
    logged_in = fields.Boolean()
    res_user = fields.Many2one('res.users')  # Primary key

    @staticmethod
    def register_user(tele_env, chat_id):
        tele_user_id = tele_env['telegram.user'].search([('chat_id', '=', chat_id)])
        if len(tele_user_id) == 0:
            login_token = res_users.random_token()
            vals = {'chat_id': chat_id, 'token': login_token}
            new_tele_user = tele_env['telegram.user'].create(vals)
        else:
            tele_user_obj = tele_env['telegram.user'].browse(tele_user_id.id)
            login_token = tele_user_obj.token  # user already exists

        return login_token

    @staticmethod
    def check_access(tele_env, chat_id, command):
        pass
        # tele_user_id = tele_env['telegram.user'].search([('chat_id', '=', chat_id)])
        # tele_user_obj = tele_env['telegram.user'].browse(tele_user_id)
        # TODO


class ResGroups(models.Model):
    _inherit = 'res.groups'

    telegram_command_id = fields.Many2one('telegram.command')

# query = """SELECT *
#            FROM mail_message as a, mail_message_res_partner_rel as b
#            WHERE a.id = b.mail_message_id
#            AND b.res_partner_id = %s""" % (5,)
# self.env.cr.execute(query)
# query_results = self.env.cr.dictfetchall()
#


def get_parameter(db_name, key):
    db = openerp.sql_db.db_connect(db_name)
    registry = openerp.registry(db_name)
    result = None
    with openerp.api.Environment.manage(), db.cursor() as cr:
        res = registry['ir.config_parameter'].search(cr, SUPERUSER_ID, [('key', '=', key)])
        if len(res) == 1:
            val = registry['ir.config_parameter'].browse(cr, SUPERUSER_ID, res[0])
            result = val.value
        elif len(res) < 1:
            _logger.debug('# WARNING. No value for key %s' % key)
            return None
    return result


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
