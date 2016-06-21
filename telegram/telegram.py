# -*- coding:utf-8 -*-

from openerp import api, models, fields
import openerp.addons.auth_signup.res_users as res_users
from openerp.http import request
from openerp import SUPERUSER_ID
import openerp
from openerp.exceptions import ValidationError


class TelegramCommand(models.Model):
    _name = "telegram.command"

    @api.model
    def telegram_listener(self, messages, bot):
        for m in messages:
            if m.content_type == 'text':
                if m.text == '/login':
                    login_token = TelegramUser.register_user(self.env, m.chat.id)
                    web_base = get_parameter(bot.db_name, 'web.base.url')
                    bot.send_message(m.chat.id, '%s/web/login/telegram?token=%s' % (web_base, login_token))
                elif m.text == '/users':
                    TelegramUser.check_access(self.env, m.chat.id, '/users')
                    users_logintime_list = [str(r.name) + ', last login at: ' + str(r.login_date) for r in
                                            self.env['res.users'].search([('name', '!=', None)])]
                    [bot.send_message(m.chat.id, r) for r in users_logintime_list]
                elif m.text == '/mails':
                    pass
                else:
                    bot.send_message(m.chat.id, 'You say ' + m.text)

    def odoo_listener(self, message, bot):
        # TODO exceptions ?
        m = message['message']
        if m['action'] == 'login':
            bot.send_message(m['chat_id'], 'Hello %s !' % m['odoo_user_name'])
            #если тут возникает ошибка то она даже в логе не отображается


class TelegramUser(models.Model):
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
        tele_user_id = tele_env['telegram.user'].search([('chat_id', '=', chat_id)])
        tele_user_obj = tele_env['telegram.user'].browse(tele_user_id)
        dumpclean(tele_user_obj.res_user.groups_id)

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
        elif len(res) > 1:
            raise ValidationError('Multiple values for %s' % key)
        elif len(res) < 1:
            print '# WARNING. No value for key:', key
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
