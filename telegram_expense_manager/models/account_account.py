from odoo import models, fields


class Account(models.Model):

    _inherit = "account.account"

    partner_id = fields.Many2one('res.partner', 'Partner')
