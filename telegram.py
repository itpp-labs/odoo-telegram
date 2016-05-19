# -*- coding:utf-8 -*-

from openerp import api, models, fields
import openerp.addons.auth_signup.res_users as res_users


class TelegramCommand(models.Model):
    _name = "telegram.command"

    @api.model
    def telegram_listener(self, messages, bot):
        print '# bot', bot
        for m in messages:
            if m.content_type == 'text':
                if m.text == '/login':
                    login_token = res_users.random_token()
                    # TODO check if already exists
                    vals = {'chat_id': m.chat.id, 'token': login_token}
                    new_tele_user = self.env['telegram.user'].create(vals)
                    # self._cr.commit()
                    bot.send_message(m.chat.id, 'http://o9_t/web/login/telegram?token=' + login_token)
                elif m.text == '/users':
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
