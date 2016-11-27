# -*- encoding: utf-8 -*-
from openerp import models, fields, api


class Channel(models.Model):

    _inherit = 'mail.group'

    telegram_subscribed = fields.Boolean(
        'Notify to Telegram', compute='_compute_subscribed',
        inverse='_set_subscribed',
        help='Get copies of messages via telegram bot. '
        'Use command /mail_channels '
        'to switch on/off notifications globally')

    telegram_subscriber_ids = fields.Many2many(
        'res.partner', 'telegram_mail_channel_partner',
        'channel_id', 'partner_id', string='Telegram Subscribers')

    @api.multi
    def _set_subscribed(self):
        cur_partner = self.env.user.partner_id
        for r in self:
            if r.telegram_subscribed:
                # new value is "subscribed"
                value = [(4, cur_partner.id, 0)]
                mail_channels_command = self.env.ref('telegram_mail.mail_channels_command', raise_if_not_found=False)
                cur_user = cur_partner.user_ids[0]
                if not cur_partner.telegram_subscribed_channel_ids \
                   and cur_user \
                   and mail_channels_command:
                    # it's first subscribed channel
                    mail_channels_command.sudo().subscribe_user(cur_user)
            else:
                value = [(3, cur_partner.id, 0)]
            r.write({'telegram_subscriber_ids': value})

    @api.multi
    def _compute_subscribed(self):
        cur_partner_id = self.env.user.partner_id.id
        for record in self:
            record.telegram_subscribed = cur_partner_id in record.telegram_subscriber_ids.ids
