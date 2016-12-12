# -*- coding: utf-8 -*-
import logging

from odoo.http import request
from odoo import http
from werkzeug import utils

_logger = logging.getLogger(__name__)


class TelegramLogin(http.Controller):

    @http.route('/web/login/telegram', type='http', auth='user')
    def do_login(self, *args, **kw):
        token = kw['token']
        command_ids = request.env['telegram.command'].search([('name', '=', '/login')]).ids

        tsession = request.env['telegram.session'].sudo().search([('token', '=', token)])
        if not tsession:
            _logger.error('Attempt to login with wrong token')
            return utils.redirect('/web')

        tsession.write({
            'user_id': request.env.uid,
            'odoo_session_sid': request.session.sid,
        })

        message = {'action': 'send_notifications',
                   'command_ids': command_ids,
                   'tsession_id': tsession.id}
        request.env['telegram.bus'].sendone(message)
        return utils.redirect('/web')
