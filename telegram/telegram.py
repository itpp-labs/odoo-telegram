# -*- coding:utf-8 -*-

import openerp
from openerp import tools
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
_logger.setLevel(logging.DEBUG)
# telebot.logger.setLevel(logging.DEBUG)


class TelegramCommand(models.Model):
    """
        Model represents Telegram commands that may be proceeded.
        Other modules can add new commands by adding some records of telegram.command model.
        Short commands gives result right after response_code is done.
        Long commands gives result after job is done, when appropriate notification appears in bus.
    """
    _name = "telegram.command"

    name = fields.Char()
    description = fields.Char(help='What command does')
    command_type = fields.Selection([('regular', 'regular'), ('cacheable', 'cacheable'), ('subscription', 'subscription')])
    universal = fields.Boolean(help='Same answer for all users or not. Meaningful only if command_type = cacheable.', default=False)
    response_code = fields.Char(help='Python code to execute task. Launched by telegram_listener')
    response_template = fields.Char(help='Message template, that user will receive immediately after he sent command')
    notify_code = fields.Char(help='Python code to get data, computed after executed response code. Launched by odoo_listener (bus)')
    notify_template = fields.Char(help='Message template, that user will receive after job is done')
    group_ids = fields.One2many('res.groups', 'telegram_command_id', help='Who can use this command')
    model_ids = fields.Many2many('ir.model', 'command_to_model_rel', 'command_id', 'model_id', help='These models changes initiates cache updates for this command')
    res_users_ids = fields.Many2many('res.users', 'command_to_user_rel', 'telegram_command_id', 'user_id', help='Subscribed users')

    @api.model
    def telegram_listener(self, messages, bot):
        # python_code execution method
        for tele_message in messages:  # messages from telegram server
            res = self.env['telegram.command'].search([('name', '=', tele_message.text)], limit=1)
            command = res[0] if len(res) > 0 else False
            if len(res) == 1:
                tele_user = self.env['telegram.user'].search([('chat_id', '=', tele_message.chat.id)])
                if command.name not in ['/login', '/help']:
                    if not tele_user.logged_in:
                        bot.send_message(tele_message.chat.id, 'You have to /login first.')
                        return
                    if not self.access_granted(command, tele_message.chat.id):
                        bot.send_message(tele_message.chat.id, 'Access denied. Command:  %s  .' % tele_message.text)
                        return
                if command.name == '/login' and tele_user.logged_in:
                    bot.send_message(tele_message.chat.id, 'You already logged in.')
                    return
                locals_dict = {'command': command, 'env': self.env, 'bot': bot, 'tele_message': tele_message}
                command_cache = bot.cache.get_value(command.id)
                need_computed_answer = True
                if command_cache:
                    need_computed_answer = self.proceed_cached_command(command_cache, command, locals_dict)
                if need_computed_answer:
                    _logger.debug('No cache. Computing answer ...')
                    safe_eval(command.response_code, globals_dict, locals_dict, mode="exec", nocopy=True)
                    self.render_and_send(command.response_template, locals_dict)
            elif len(res) > 1:
                raise ValidationError('Multiple values for %s' % res)
            else:
                bot.send_message(tele_message.chat.id, 'No such command:  %s  . Use /help to see all commands.' % tele_message.text)

    def proceed_cached_command(self, command_cache, command, locals_dict):
        _logger.debug('got cache for this command')
        _logger.debug(command_cache)
        need_computed_answer = True
        tele_message = locals_dict['tele_message']
        if command.universal:
            locals_dict['data'] = command_cache
            self.render_and_send(command.response_template, locals_dict)
            need_computed_answer = False
            _logger.debug('Sent answer from cache')
        else:
            for usr_id in command_cache:
                locals_dict['data'] = command_cache[usr_id]
                tele_user = self.env['telegram.user'].search([('id', '=', usr_id),
                                                              ('chat_id', '=', tele_message.chat.id)])
                if len(tele_user) > 0:
                    self.render_and_send(command.response_template, locals_dict)
                need_computed_answer = False
        return need_computed_answer

    # bus listener
    @api.model
    def odoo_listener(self, message, bot):
        bus_message = message['message']  # message from bus, not from telegram server.
        registry = openerp.registry(bot.db_name)
        db = openerp.sql_db.db_connect(bot.db_name)
        with openerp.api.Environment.manage(), db.cursor() as cr:
            _logger.debug('bus_message')
            _logger.debug(bus_message)
            if bus_message['action'] == 'update_cache':
                self.update_cache(bus_message, bot)
            elif bus_message['action'] == 'handle_subscriptions':
                self.handle_subscriptions(bus_message, bot)
            else:
                command_id = registry['telegram.command'].search(cr, SUPERUSER_ID, [('name', '=', bus_message['action'])])
                command = registry['telegram.command'].browse(cr, SUPERUSER_ID, command_id)
                if len(command) == 1:
                    if command.notify_code:
                        locals_dict = {'bot': bot, 'bus_message': bus_message}
                        safe_eval(command.notify_code, globals_dict, locals_dict, mode="exec", nocopy=True)
                        _logger.debug('locals_dict')
                        _logger.debug(locals_dict)
                        command.render_and_send(command.notify_template, locals_dict)
                    else:
                        pass  # No notify_code for this command. Response code is optional.
                elif len(command) > 1:
                    raise ValidationError('Multiple values for %s' % command)

    def render_and_send(self, template, locals_dict):
        """Response or notify user. template - xml to render with locals_dict."""
        bot = locals_dict['bot']
        tele_message = locals_dict['tele_message'] if 'tele_message' in locals_dict else False
        bus_message = locals_dict['bus_message'] if 'bus_message' in locals_dict else False
        qweb = self.pool['ir.qweb']
        context = QWebContext(self._cr, self._uid, {})
        ctx = context.copy()
        ctx.update({'data': locals_dict['data']})
        try:
            dom = etree.fromstring(template)
            _logger.debug('locals_dict')
            _logger.debug(locals_dict)
            if 'notify_user_ids' in locals_dict:
                notify_users = set(self.res_users_ids.ids).intersection(set(locals_dict['notify_user_ids']))
                if self.universal:
                    rend = qweb.render_node(dom, ctx)
                    _logger.debug('render_and_send(): ' + rend)
                for notify_user in notify_users:
                    telegram_user = self.env['telegram.user'].search([('res_user', '=', notify_user)])
                    if not self.universal:
                        ctx['data']['user_id'] = notify_user
                        rend = qweb.render_node(dom, ctx)
                        _logger.debug('render_and_send(): ' + rend)
                    bot.send_message(telegram_user.chat_id, rend, parse_mode='HTML')
            else:
                chat_id = bus_message['chat_id'] if bus_message else tele_message.chat.id
                rend = qweb.render_node(dom, ctx)
                _logger.debug('render_and_send(): ' + rend)
                bot.send_message(chat_id, rend, parse_mode='HTML')
        except:
            _logger.critical(sys.exc_info()[0])

    # ir.actions.server methods:
    @api.model
    def action_telegram_update_cache(self):
        # Called by ir.actions.server
        context = self._context
        found_cacheable_commands = self.env['telegram.command'].search([('model_ids.model', '=', context['active_model']), ('command_type', '=', 'cacheable')])
        if len(found_cacheable_commands):
            _logger.debug('update_cache_bus_message(): commands will got cache update:')
            _logger.debug(found_cacheable_commands)
            message = {'action': 'update_cache', 'update_cache': True, 'model': context['active_model'], 'found_commands_ids': found_cacheable_commands.ids}
            self.env['telegram.bus'].sendone('telegram_channel', message)

    @api.model
    def action_telegram_handle_subscriptions(self):
        # Called by ir.actions.server
        _logger.debug('telegram_manage_subscriptions_event')
        context = self._context
        found_subscription_commands = self.env['telegram.command'].search([('model_ids.model', '=', context['active_model']), ('command_type', '=', 'subscription')])
        _logger.debug(found_subscription_commands)
        if len(found_subscription_commands):
            message = {'action': 'handle_subscriptions', 'active_id': context['active_id'], 'update_cache': False, 'model': context['active_model'], 'found_commands_ids': found_subscription_commands.ids}
            self.env['telegram.bus'].sendone('telegram_channel', message)

    # bus reaction methods
    def update_cache(self, bus_message, bot):
        _logger.debug('update_cache() - command from bus')
        for command_id in bus_message['found_commands_ids']:
            command = self.env['telegram.command'].browse(command_id)
            locals_dict = {'bot': bot, 'env': self.env,'bus_message': bus_message}
            if command.universal:
                safe_eval(command.response_code, globals_dict, locals_dict, mode="exec", nocopy=True)
                bot.cache.set_value(command_id, locals_dict['data'])
            else:
                users = self.env['res.user'].search([('groups_ids', 'in', command.group_ids)])
                for user in users:
                    safe_eval(command.response_code, globals_dict, locals_dict, mode="exec", nocopy=True)
                    bot.cache.set_value(command_id, locals_dict['data'], user.id)

    def handle_subscriptions(self, bus_message, bot):
        _logger.debug('handle_subscriptions() - called by bus')
        for command_id in bus_message['found_commands_ids']:
            command = self.env['telegram.command'].browse(command_id)
            locals_dict = {'bot': bot, 'command': command, 'self': self, 'env': self.env,'bus_message': bus_message}
            try:
                safe_eval(command.notify_code, globals_dict, locals_dict, mode="exec", nocopy=True)
            except:
                _logger.warning(sys.exc_info()[0])
            command.render_and_send(command.notify_template, locals_dict)

    # other methods
    def access_granted(self, command, chat_id):
        # granted or not ?
        command_groups = set(self.env['res.groups'].search([('telegram_command_id', '=', command.id)]))
        if len(command_groups) == 0:
            return True  # If no groups than every one can use this command
        tele_user = self.env['telegram.user'].search([('chat_id', '=', chat_id)])
        user_groups = set(tele_user.res_user.groups_id)
        if len(command_groups.intersection(user_groups)):
            return True
        return False


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
            vals = {'chat_id': chat_id, 'token': login_token, 'logged_in': False}
            new_tele_user = tele_env['telegram.user'].create(vals)
        else:
            tele_user_obj = tele_env['telegram.user'].browse(tele_user_id.id)
            login_token = tele_user_obj.token  # user already exists

        return login_token

    @staticmethod
    def logout(env, chat_id):
        tele_user_id = env['telegram.user'].search([('chat_id', '=', chat_id)])
        tele_user_id.logged_in = False


class ResGroups(models.Model):
    _inherit = 'res.groups'

    telegram_command_id = fields.Many2one('telegram.command')



    # query = """SELECT *


globals_dict = {
    'datetime': datetime,
    'dateutil': dateutil,
    'time': time,
    '_logger': _logger,
    'tools': tools,
    'TelegramUser': TelegramUser
}


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


