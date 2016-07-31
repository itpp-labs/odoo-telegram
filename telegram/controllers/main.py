# -*- coding:utf-8 -*-

from openerp import SUPERUSER_ID
from openerp.http import request
from openerp import http
from werkzeug import utils


class TelegramLogin(http.Controller):

    @http.route('/web/login/telegram', type='http', auth='user')
    def do_login(self, *args, **kw):
        token = kw['token']
        command_ids = request.env['telegram.command'].search([('name', '=', '/login')]).ids

        tsession = request.env['telegram.session'].sudo().search([('token', '=', token)])
        if not tsession:
            return utils.redirect('/web')

        tsession.user_id = request.env.uid

        message = {'action': 'send_notifications',
                   'command_ids': command_ids,
                   'tsession_id': tsession.id}
        request.env['telegram.bus'].sendone('telegram_channel', message)
        return utils.redirect('/web')
