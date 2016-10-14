# -*- coding: utf-8 -*-

from StringIO import StringIO
import base64
import datetime
import dateutil
import time
import logging
from telebot.apihelper import ApiException, _convert_markup
from telebot import types, TeleBot
from lxml import etree
from openerp import tools
from openerp import api, models, fields
import openerp.addons.auth_signup.res_users as res_users
from openerp.tools.safe_eval import safe_eval
from openerp.tools.translate import _
from openerp.addons.base.ir.ir_qweb import QWebContext

_logger = logging.getLogger(__name__)


class TelegramCommand(models.Model):
    """
        Model represents Telegram commands that may be proceeded.
        Other modules can add new commands by adding some records of telegram.command model.
        Short commands gives result right after response_code is done.
        Long commands gives result after job is done, when appropriate notification appears in bus.
    """
    _name = "telegram.command"
    _order = "sequence"

    name = fields.Char('Name', help='Command name. Usually starts with slash symbol, e.g. "/mycommand"', required=True)
    description = fields.Char('Description', help='What command does. It will be used in /help command')
    sequence = fields.Integer(default=16)
    type = fields.Selection([('normal', 'Normal'), ('cacheable', 'Normal (with caching)'), ('subscription', 'Subscription')], help='''
* Normal - usual request-response commands
* Normal (with caching) - prepares and caches response to send it immediately after requesting
* Subscription - allows to subscribe to events or notifications

    ''', default='normal', required=True)
    universal = fields.Boolean(help='Same answer for all users or not.', default=False)
    response_code = fields.Text(help='''Code to be executed before rendering Response Template. ''')
    response_template = fields.Text(help='Template for the message, that user will receive immediately after sending command')
    post_response_code = fields.Text(help='Python code to be executed after sending response')
    notification_code = fields.Text(help='''Code to be executed before rendering Notification Template

Vars that can be created to be handled by telegram module
* notify_user_ids - by default all subscribers get notification. With notify_user_ids you can specify list of users who has to receive notification. Then only ones who subscribed and are specified in notify_user_ids will receive notification.

Check Help Tab for the rest variables.

    ''')
    notification_template = fields.Text(help='Template for the message, that user will receive when event happens')
    group_ids = fields.Many2many('res.groups', string="Access Groups", help='Who can use this command. Set empty list for public commands (e.g. /login)', default=lambda self: [self.env.ref('base.group_user').id])
    model_ids = fields.Many2many('ir.model', 'command_to_model_rel', 'command_id', 'model_id', string="Related models", help='Is used by Server Action to find commands to proceed')
    user_ids = fields.Many2many('res.users', 'command_to_user_rel', 'telegram_command_id', 'user_id', string='Subscribed users')
    menu_id = fields.Many2one('ir.ui.menu', 'Related Menu', help='Menu that can be used in command, for example to make search')

    _sql_constraints = [
        ('command_name_uniq', 'unique (name)', 'Command name must be unique!'),
    ]

    @api.model
    def telegram_listener(self, messages, bot):
        # python_code execution method
        for tele_message in messages:  # messages from telegram server
            tsession = self.env['telegram.session'].get_session(tele_message.chat.id)

            command = self.env['telegram.command'].sudo(tsession.get_user()).search([('name', '=', tele_message.text)], limit=1)
            if not command:
                not_found = {'html': _("There is no such command or you don't have access:  <i>%s</i>.  \n Use /help to see all available for you commands.") % tele_message.text}
                self.send(bot, not_found, tsession)
                if not tsession.user_id:
                    self.send(bot, {'html': _('Or try to /login.')}, tsession)
                return

            response = None
            locals_dict = {}
            if command.type == 'subscription':
                if not tsession.user_id:
                    self.send(bot, {'html': _('You have to /login first.')}, tsession)
                    return

                if tsession.user_id.id in command.user_ids.ids:
                    locals_dict['subscribed'] = False
                    command.sudo().write({'user_ids': [(3, tsession.user_id.id, 0)]})
                else:
                    locals_dict['subscribed'] = True
                    command.sudo().write({'user_ids': [(4, tsession.user_id.id, 0)]})

            if command.type == 'cacheable':
                response = bot.cache.get_value(command, tsession)
                if response:
                    _logger.debug('Cached response found for command %s' % tele_message.text)
                else:
                    _logger.debug('No cache found for command %s' % tele_message.text)

            if not response:
                response = command.get_response(locals_dict, tsession)
                bot.cache.set_value(command, response, tsession)
            self.send(bot, response, tsession)
            command.eval_post_response(tsession)

    # bus listener
    @api.model
    def odoo_listener(self, message, odoo_thread, bot):
        bus_message = message['message']  # message from bus, not from telegram server.
        _logger.debug('bus_message')
        _logger.debug(bus_message)
        if bus_message['action'] == 'update_cache':
            if bot:
                self.update_cache(bus_message, bot)
        elif bus_message['action'] == 'send_notifications':
            self.send_notifications(bus_message, bot)

    @api.multi
    def get_response(self, locals_dict=None, tsession=None):
        self.ensure_one()
        locals_dict = self._eval(self.response_code, locals_dict=locals_dict, tsession=tsession)
        return self._render(self.response_template, locals_dict, tsession)

    @api.multi
    def eval_post_response(self, tsession):
        self.ensure_one()
        if self.post_response_code:
            return self._eval(self.post_response_code, tsession=tsession)

    @api.multi
    def eval_notification(self, event, tsession):
        self.ensure_one()
        return self._eval(self.notification_code, locals_dict={'event': event}, tsession=tsession)

    @api.multi
    def render_notification(self, locals_dict, tsession=None):
        self.ensure_one()
        return self._render(self.notification_template, locals_dict, tsession)

    @api.multi
    def _get_globals_dict(self):
        return {
            'datetime': datetime,
            'dateutil': dateutil,
            'time': time,
            '_logger': _logger,
            'tools': tools,
            'types': types,
        }

    @api.multi
    def _eval(self, code, locals_dict=None, tsession=None):
        _logger.debug("_eval locals_dict: %s" % locals_dict)
        t0 = time.time()
        locals_dict = locals_dict or {}
        user = tsession and tsession.get_user()
        locals_dict.update({
            'command': self.sudo(user),
            'env': self.env(user=user),
            'data': {},
            'photos': [],
            'callback_data': locals_dict.get('callback_data', False),
            'tsession': tsession})
        globals_dict = self._get_globals_dict()
        if code:
            safe_eval(code, globals_dict, locals_dict, mode="exec", nocopy=True)
            eval_time = time.time() - t0
            _logger.debug('Eval in %.2fs \nlocals_dict:\n%s\nCode:\n%s\n', eval_time, locals_dict, code)
        return locals_dict

    def _qcontext(self, locals_dict, tsession):
        qcontext = QWebContext(self._cr, self._uid, {})
        qcontext['data'] = locals_dict['data']
        qcontext['subscribed'] = locals_dict.get('subscribed')
        qcontext['tsession'] = tsession
        return qcontext

    def _render(self, template, locals_dict, tsession):
        t0 = time.time()
        dom = etree.fromstring(template)
        qcontext = self._qcontext(locals_dict, tsession)
        html = self.pool['ir.qweb'].render_node(dom, qcontext)
        render_time = time.time() - t0
        _logger.debug('Render in %.2fs\n qcontext:\n%s \nTemplate:\n%s\n', render_time, qcontext, template)
        ret = {'photos': [],
               'markup': _convert_markup(locals_dict.get('data', {}).get('reply_markup', {})),
               'html': html}
        for photo in locals_dict.get('photos', []):
            if photo.get('type') == 'file':
                f = photo['data']
            else:
                # type is 'base64' by default'
                f = StringIO(base64.b64decode(photo['data']))
                f.name = photo.get('filename', 'item.png')
            ret['photos'].append({'file': f})
        return ret

    @api.model
    def send(self, bot, rendered, tsession):
        try:
            self._send(bot, rendered, tsession)
            return True
        except ApiException:
            # TODO remove tsession in case of following error:
            # [{"ok":false,"error_code":400,"description":"Bad Request: chat not found"}]
            _logger.error('Cannot send message', exc_info=True)
            return False

    @api.model
    def _send(self, bot, rendered, tsession):
        reply_markup = rendered.get('markup', None)
        _logger.debug('_send rendered %s' % rendered)
        _logger.debug('reply_markup %s' % reply_markup)
        if rendered.get('html'):
            _logger.debug('Send:\n%s', rendered.get('html'))
            bot.send_message(tsession.chat_ID, rendered.get('html'), parse_mode='HTML', reply_markup=reply_markup)
        if rendered.get('photos'):
            _logger.debug('send photos %s' % len(rendered.get('photos')))
            for photo in rendered.get('photos'):
                if photo.get('file_id'):
                    try:
                        _logger.debug('Send photo by file_id')

                        bot.send_photo(tsession.chat_ID, photo['file_id'])
                        continue
                    except ApiException:
                        _logger.debug('Sending photo by file_id is failed', exc_info=True)
                photo['file'].seek(0)
                _logger.debug('photo[file] %s ' % photo['file'])
                res = bot.send_photo(tsession.chat_ID, photo['file'])
                photo['file_id'] = res.photo[0].file_id

    @api.multi
    def get_graph_data(self):
        self.ensure_one()
        action = self.menu_id.action
        if action._name != 'ir.actions.act_window':
            return []
        domain, filters = self.get_action_domain(action)
        graph_view = self.env[action.res_model].fields_view_get(view_type='graph')['arch']
        graph_view = etree.fromstring(graph_view)

        graph_config = {
            'stacked': graph_view.attrib.get('stacked'),
            'row': [],
            'col': [],
            'measure': None,
            'fields': []
        }
        for el in graph_view:
            if el.tag != 'field':
                continue
            f = el.attrib
            if f['type'] == 'row' or f['type'] == 'col':
                value = f['name']
                graph_config['fields'].append(value)
                if f.get('interval'):
                    value += ':' + f.get('interval')
                graph_config[f['type']].append(value)
            elif f['type'] == 'measure':
                value = f['name']
                graph_config['measure'] = value
                graph_config['fields'].append(value)

        res = self.env[action.res_model].read_group(
            domain,
            fields=graph_config['fields'],
            groupby=graph_config['row'] + graph_config['col'],
            lazy=False,
        )

        measure_field = graph_config.get('measure')
        xlabels = []
        # e.g. Stage in CRM Pipeline
        xlabel_field = graph_config['row'][0]

        dlabels = []
        # e.g. Month in CRM Pipeline
        dlabel_field = graph_config['col'][0]
        for r in res:
            for a, f in [(xlabels, xlabel_field), (dlabels, dlabel_field)]:
                # a - array
                # f - field name
                # v = value
                v = r[f]
                if v not in a:
                    a.append(v)

        # res_index = {x_value: {d_value}}
        res_index = dict([(x_value, {}) for x_value in xlabels])
        for r in res:
            res_index[r[xlabel_field]][r[dlabel_field]] = r[measure_field]
        # data_lines = {d_value: {'values': {x_value}}}
        data_lines = dict([(d_value, {'values': []}) for d_value in dlabels])
        for d_value, data in data_lines.items():
            for x_value in xlabels:
                data['values'].append(res_index[x_value].get(d_value, 0))
        res = {
            'filters': filters,
            'x_labels': list(xlabels),
            'data_lines': data_lines,
            'stacked': graph_config['stacked']
        }
        return res

    @api.model
    def get_action_domain(self, action):
        used_filters = []
        eval_vars = {'uid': self.env.uid}
        filters = self.env['ir.filters'].get_filters(action.res_model, action.id)
        personal_filter = None

        # get_default_filter function from js:
        for f in filters:
            if f['user_id'] and f['is_default']:
                personal_filter = f
                break

        if not personal_filter:
            for f in filters:
                if not f['user_id'] and f['is_default']:
                    personal_filter = f
                    break

        if personal_filter:
            personal_filter['string'] = personal_filter['name']
            default_domains = [personal_filter['domain']]
            used_filters = [personal_filter]
        else:
            # find filter from context, i.e. the same as UI works
            default_domains = []
            # parse search view
            search_view = self.env[action.res_model].fields_view_get(view_id=action.search_view_id.id, view_type='search')['arch']
            search_view_filters = {}
            for el in etree.fromstring(search_view):
                if el.tag != 'filter':
                    continue
                f = el.attrib
                search_view_filters[f['name']] = f

            # proceed context
            action_context = safe_eval(action.context, eval_vars)
            for k, v in action_context.items():
                if not k.startswith('search_default'):
                    continue
                filter_name = k.split('search_default_')[1]
                filter = search_view_filters[filter_name]
                default_domains.append(filter['domain'])
                used_filters.append(filter)

        # eval and combine default_domains into one
        domain = []
        for d in default_domains:
            domain += safe_eval(d, eval_vars)
        return domain, used_filters

    # ir.actions.server methods:
    @api.model
    def action_update_cache(self):
        # Called by ir.actions.server
        context = self._context
        cacheable_commands = self.env['telegram.command'].search([('model_ids.model', '=', context['active_model']), ('type', '=', 'cacheable')])
        if len(cacheable_commands):
            _logger.debug('update_cache_bus_message(): commands will got cache update:')
            _logger.debug(cacheable_commands)
            message = {
                'action': 'update_cache',
                'command_ids': cacheable_commands.ids}
            self.env['telegram.bus'].sendone('telegram_channel', message)

    @api.model
    def action_handle_subscriptions(self, id_or_xml_id=None):
        _logger.debug('telegram_manage_subscriptions_event')
        context = self._context
        if id_or_xml_id:
            # called by ir.cron
            if not isinstance(id_or_xml_id, (int, long)):
                subscription_commands = self.env.ref(id_or_xml_id)
            else:
                subscription_commands = self.env['telegram.command'].browse(id_or_xml_id)
        else:
            # Called by base.action.rule via ir.actions.server
            subscription_commands = self.env['telegram.command'].search([('model_ids.model', '=', context['active_model']), ('type', '=', 'subscription')])
        _logger.debug('subscription_commands %s' % [c.name for c in subscription_commands])
        event = dict((k, context.get(k)) for k in ['active_model', 'active_id', 'active_ids'])
        if len(subscription_commands):
            message = {
                'action': 'send_notifications',
                'event': event,
                'command_ids': subscription_commands.ids
            }
            self.env['telegram.bus'].sendone('telegram_channel', message)

    # bus reaction methods
    def update_cache(self, bus_message, bot):
        _logger.debug('update_cache() - command from bus')
        for command in self.browse(bus_message['command_ids']):
            if command.universal:
                response = command.get_response()
                bot.cache.set_value(command, response)
            else:
                res = self.env['telegram.session'].search([('user_id.groups_ids', 'in', command.group_ids)])
                for tsession in res:
                    response = command.get_response(tsession=tsession)
                    bot.cache.set_value(command, response, tsession)

    def send_notifications(self, bus_message, bot):
        _logger.debug('send_notifications() - called by bus')
        tsession = None
        if bus_message.get('tsession_id'):
            tsession = self.env['telegram.session'].browse(bus_message.get('tsession_id'))
        for command in self.env['telegram.command'].browse(bus_message['command_ids']):
            locals_dict = command.eval_notification(bus_message.get('event'), tsession)

            if command.type == 'subscription':
                notify_user_ids = set(command.user_ids.ids)
                if 'notify_user_ids' in locals_dict:
                    notify_user_ids = notify_user_ids.intersection(set(locals_dict.get('notify_user_ids', [])))

                notify_sessions = self.env['telegram.session'].search([('user_id', 'in', list(notify_user_ids))])

            else:
                notify_sessions = [tsession]

            if not notify_sessions:
                return

            if command.universal:
                rendered = command.render_notification(locals_dict)

            for tsession in notify_sessions:
                if not command.universal:
                    rendered = command.render_notification(locals_dict, tsession)
                command.send(bot, rendered, tsession)


class IrConfigParameter(models.Model):
    _inherit = 'ir.config_parameter'

    @api.model
    def proceed_telegram_configs(self, dbname=False):
        # invoked by ir.actions.server
        _logger.debug('telegram_proceed_ir_config')
        message = {}
        active_id = self._context['active_id']
        parameter = self.env['ir.config_parameter'].browse(active_id)
        _logger.debug('parameter = %s' % parameter)
        if parameter.key == 'telegram.token':
            message['action'] = 'token_changed'
        elif parameter.key == 'telegram.num_odoo_threads':
            message['action'] = 'odoo_threads_changed'
        elif parameter.key == 'telegram.num_telegram_threads':
            message['action'] = 'telegram_threads_changed'
        if message:
            message['dbname'] = self._cr.dbname
            self.env['telegram.bus'].sendone('telegram_channel', message)


class TelegramSession(models.Model):
    _name = "telegram.session"

    chat_ID = fields.Char()
    token = fields.Char(default=lambda self: res_users.random_token())
    logged_in = fields.Boolean()
    user_id = fields.Many2one('res.users')

    @api.multi
    def get_user(self):
        self.ensure_one()
        return self.user_id or self.env.ref('base.public_user')

    @api.model
    def get_session(self, chat_ID):
        tsession = self.env['telegram.session'].search([('chat_ID', '=', chat_ID)])
        if not tsession:
            tsession = self.env['telegram.session'].create({'chat_ID': chat_ID})
        return tsession
