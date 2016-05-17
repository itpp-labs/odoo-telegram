# -*- coding:utf-8 -*-

from openerp import api, models, fields
import threading
import os
import time
import openerp.addons.auth_signup.res_users as res_users
from openerp import http
from openerp.http import request
import werkzeug
import openerp
from openerp import SUPERUSER_ID
import telebot

class TelegramCommand(models.Model):
    _name = "telegram.command"

    @api.model
    def listener(self, messages, bot):
        for m in messages:
            if m.content_type == 'text':
                if m.text == '/login':
                    login_token = res_users.random_token()
                    # TODO check if already exists
                    vals = {'chat_id': m.chat.id, 'token': login_token}
                    new_tele_user = self.env['telegram.user'].create(vals)
                    self._cr.commit()
                    bot.send_message(m.chat.id, 'http://o9_t/web/login/telegram?token=' + login_token)
                elif m.text == '/users':
                    users_logintime_list = [str(r.name) + ', last login at: ' + str(r.login_date) for r in
                                            self.env['res.users'].search([('name', '!=', None)])]
                    [bot.send_message(m.chat.id, r) for r in users_logintime_list]
                elif m.text == '/mails':
                    pass
                else:
                    bot.send_message(m.chat.id, 'You say ' + m.text)


class TelegramLogin(http.Controller):

    @http.route('/web/login/telegram', type='http', auth='user')
    def do_login(self, *args, **kw):
        cr, uid, context, pool = request.cr, request.uid, request.context, request.registry
        tele_user_id = pool['telegram.user'].search(cr, SUPERUSER_ID, [('token', '=', kw['token'])])
        if len(tele_user_id) == 1:
            tele_user_obj = pool['telegram.user'].browse(cr, SUPERUSER_ID, tele_user_id)
            tele_user_obj.res_user = pool['res.users'].browse(cr, SUPERUSER_ID, uid)
            tele_user_obj.logged_in = True
            # TMP
            token = '223555999:AAFJlG9UMLSlZIf9uqpHiOkilyDJrqAU5hA'
            bot = telebot.TeleBot(token, threaded=True)
            bot.send_message(tele_user_obj.chat_id, 'Logged successfully!')
        return werkzeug.utils.redirect('/web/')

class TelegramUser(models.Model):
    _name = "telegram.user"

    chat_id = fields.Char()
    token = fields.Char()
    logged_in = fields.Boolean()
    res_user = fields.Many2one('res.users')


# query = """SELECT *
#            FROM mail_message as a, mail_message_res_partner_rel as b
#            WHERE a.id = b.mail_message_id
#            AND b.res_partner_id = %s""" % (5,)
# self.env.cr.execute(query)
# query_results = self.env.cr.dictfetchall()
#


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
