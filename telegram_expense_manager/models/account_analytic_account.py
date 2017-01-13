# -*- coding: utf-8 -*-
from odoo import models, fields


class AccountAnalyticAccount(models.Model):

    _inherit = 'account.analytic.account'

    partner_id = fields.Many2one(index=True)
    liquidity_id = fields.Many2one(
        'account.analytic.account',
        string='Default liquidity',
        help='Default liquidity analytic account '
        'for expense or income accounts')
