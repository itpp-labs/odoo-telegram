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
        cur_partner_id = self.env.user.partner_id.id
        for r in self:
            if r.telegram_subscribed:
                value = [(4, cur_partner_id, 0)]
                # TODO: check global subscription and activate if it's off
            else:
                value = [(3, cur_partner_id, 0)]
            print '_set_subscribed', value
            r.write({'telegram_subscriber_ids': value})

    @api.multi
    def _compute_subscribed(self):
        cur_partner_id = self.env.user.partner_id.id
        for record in self:
            print '_compute_subscribed', cur_partner_id,  record.telegram_subscriber_ids.ids
            record.telegram_subscribed = cur_partner_id in record.telegram_subscriber_ids.ids
