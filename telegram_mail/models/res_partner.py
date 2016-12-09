# -*- coding: utf-8 -*-
from openerp import models, fields


class ResPartner(models.Model):
    _inherit = "res.partner"

    telegram_subscribed_channel_ids = fields.Many2many(
        'mail.group', 'telegram_mail_channel_partner',
        'partner_id', 'channel_id', string='Telegram Channels',
        help='The partner is notified about new messages from these channels. '
        'Notifications could be switched off globally by using /mail_channels command. '
    )
