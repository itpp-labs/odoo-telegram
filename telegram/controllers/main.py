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
        command = request.env['telegram.command']\
                         .with_context(active_test=False)\
                         .search([('name', '=', '/login')])

        tsession = request.env['telegram.session'].sudo().search([('token', '=', token)])
        if not tsession:
            _logger.error('Attempt to login with wrong token')
            return utils.redirect('/web')

        tsession.write({
            'user_id': request.env.uid,
            'odoo_session_sid': request.session.sid,
        })
        command.send_notifications(tsession=tsession)
        return utils.redirect('/web')
