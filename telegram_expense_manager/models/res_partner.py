# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class Partner(models.Model):
    _inherit = "res.partner"

    def _default_em_currency(self):
        return self.env.user.company_id.currency_id

    em_currency_id = fields.Many2one('res.currency',
                                     string="Base currency for personal expense management",
                                     ondelete='restrict',
                                     default=_default_em_currency)
