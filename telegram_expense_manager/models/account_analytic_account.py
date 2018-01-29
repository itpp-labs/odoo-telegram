# -*- coding: utf-8 -*-
from odoo import models, fields, api


class AccountAnalyticAccount(models.Model):

    _inherit = 'account.analytic.account'

    partner_id = fields.Many2one(index=True)
    liquidity_id = fields.Many2one(
        'account.analytic.account',
        string='Default liquidity',
        help='Default liquidity analytic account '
        'for expense or income accounts')

    @api.multi
    def get_user_tags(self):
        self.ensure_one()
        com = self.env['telegram.command']
        exclude_tags = \
            self.env.ref(com.TAG_LIQUIDITY) + \
            self.env.ref(com.TAG_PAYABLE) + \
            self.env.ref(com.TAG_RECEIVABLE)
        return self.tag_ids - exclude_tags

    @api.multi
    def _compute_move_debit_credit_balance(self):
        """based on https://github.com/odoo/odoo/blame/10.0/addons/analytic/models/analytic_account.py
        account_id is replaced to analytic_account_id,
        account.analytic.line is replaced to account.move.line
        """
        analytic_line_obj = self.env['account.move.line']
        domain = [('analytic_account_id', 'in', self.mapped('id'))]
        if self._context.get('from_date', False):
            domain.append(('date', '>=', self._context['from_date']))
        if self._context.get('to_date', False):
            domain.append(('date', '<=', self._context['to_date']))

        account_amounts = analytic_line_obj.search_read(domain, ['analytic_account_id', 'debit', 'credit'])
        analytic_account_ids = set([line['analytic_account_id'][0] for line in account_amounts])
        data_debit = {analytic_account_id: 0.0 for analytic_account_id in analytic_account_ids}
        data_credit = {analytic_account_id: 0.0 for analytic_account_id in analytic_account_ids}
        for account_amount in account_amounts:
            data_debit[account_amount['analytic_account_id'][0]] += account_amount['debit']
            data_credit[account_amount['analytic_account_id'][0]] += account_amount['credit']

        for account in self:
            account.move_debit = data_debit.get(account.id, 0.0)
            account.move_credit = data_credit.get(account.id, 0.0)
            account.move_balance = account.move_debit - account.move_credit

    move_balance = fields.Monetary(compute='_compute_move_debit_credit_balance', string='Balance')
    move_debit = fields.Monetary(compute='_compute_move_debit_credit_balance', string='Debit')
    move_credit = fields.Monetary(compute='_compute_move_debit_credit_balance', string='Credit')
    currency_ids = fields.Many2many("res.currency", "analytic_account_currency_rel")

    @api.multi
    def _attach_new_currency(self, currency):
        for record in self:
            if currency not in record.currency_ids:
                record.currency_ids = [(4, currency.id)]

    @api.multi
    def get_currency_balance(self, currency=None):
        AccountMoveLine = self.env['account.move.line']
        domain = [('analytic_account_id', 'in', self.mapped('id'))]
        if self._context.get('from_date', False):
            domain.append(('date', '>=', self._context['from_date']))
        if self._context.get('to_date', False):
            domain.append(('date', '<=', self._context['to_date']))
        if currency:
            domain.append(('currency_id', '=', currency.id))
        else:
            domain.append(('currency_id', '=', False))

        account_amounts = AccountMoveLine.search_read(domain, ['analytic_account_id', 'balance'])
        move_balance = 0.0
        for account_amount in account_amounts:
            move_balance += account_amount['balance']

        return move_balance
