# -*- coding:utf-8 -*-

from openerp import SUPERUSER_ID
from openerp.http import request
from openerp import http
import werkzeug


class TelegramLogin(http.Controller):

    @http.route('/web/login/telegram', type='http', auth='user')
    def do_login(self, *args, **kw):
        cr, uid, context, pool = request.cr, request.uid, request.context, request.registry
        tele_user_id = pool['telegram.user'].search(cr, SUPERUSER_ID, [('token', '=', kw['token'])])
        if len(tele_user_id) == 1:
            tele_user_obj = pool['telegram.user'].browse(cr, SUPERUSER_ID, tele_user_id)
            tele_user_obj.res_user = pool['res.users'].browse(cr, SUPERUSER_ID, uid)
            tele_user_obj.logged_in = True
            pool['telegram.bus'].sendone(cr, SUPERUSER_ID, 'telegram_chanel', 'check_messages')
            # # TMP
            # token = '223555999:AAFJlG9UMLSlZIf9uqpHiOkilyDJrqAU5hA'
            # bot = telebot.TeleBot(token, threaded=True)
            # bot.send_message(tele_user_obj.chat_id, 'Logged successfully!')
        return werkzeug.utils.redirect('/web/')