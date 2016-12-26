from odoo import models, fields


class AccountAnalyticAccount(models.Model):

    _inherit = 'account.analytic.account'

    partner_id = fields.Many2one(index=True)
