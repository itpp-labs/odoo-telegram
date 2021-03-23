# -*- coding: utf-8 -*-

from odoo import api, fields, models, tools, _


class CurrencyAlias(models.Model):
    _name = "res.currency.alias"

    name = fields.Char(string='Currency Alias')
    _sql_constraints = [

        ('unique_name', 'unique (name)', 'The currency alias must be unique!'),
    ]

    currency_id = fields.Many2one('res.currency', string='Currency', readonly=True)


class Currency(models.Model):
    _inherit = "res.currency"

    alias_ids = fields.One2many('res.currency.alias', 'currency_id', string='Aliases')
