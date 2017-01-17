# -*- coding: utf-8 -*-
from odoo import models, fields, api


class Schedule(models.Model):

    _name = "account.schedule"

    def _type_tags(self):
        return [
            self.env.ref(self.env['telegram.command'].TAG_RECEIVABLE).id,
            self.env.ref(self.env['telegram.command'].TAG_LIQUIDITY).id,
            self.env.ref(self.env['telegram.command'].TAG_PAYABLE).id,
        ]

    partner_id = fields.Many2one(
        'res.partner',
        string='Partner',
        required=True,
        default=lambda self: self.env.user.partner_id,
    )

    from_tag_id = fields.Many2one(
        'account.analytic.tag',
        string='Type',
        required=True,
        domain=lambda self: [('id', 'in', self._type_tags())]
    )

    from_analytic_id = fields.Many2one(
        'account.analytic.account',
        string='Analytic',
        domain="""[
            ('partner_id', '=', partner_id),
            ('tag_ids', '=', from_tag_id),
        ]"""
    )

    to_tag_id = fields.Many2one(
        'account.analytic.tag',
        string='Type',
        required=True,
        domain=lambda self: [('id', 'in', self._type_tags())]
    )

    to_analytic_id = fields.Many2one(
        'account.analytic.account',
        string='Analytic',
        domain="""[
            ('partner_id', '=', partner_id),
            ('tag_ids', '=', to_tag_id),
        ]"""
    )

    periodicity_type = fields.Selection([
        ('day', 'Daily'),
        ('week', 'Weekly'),
        ('month', 'Monthly'),
    ], string='Periodicity Type')

    periodicity_amount = fields.Integer('Periodicity Amount')
    currency_id = fields.Many2one(
        'res.currency',
        string='Account Currency',
        default=lambda self: self.env.user.company_id.currency_id,
    )
    amount = fields.Monetary('Amount', help='Amount of money to be transfered')
    notify = fields.Boolean('Notify on transfer', help='Notify user in telegram about created transfer')
