# -*- coding: utf-8 -*-
from odoo import models, api
from odoo.exceptions import AccessError
from odoo.tools.translate import _

TYPE_LIQUIDITY = 'account.data_account_type_liquidity'
TYPE_PAYABLE = 'account.data_account_type_payable'
TYPE_RECEIVABLE = 'account.data_account_type_receivable'

TAG_LIQUIDITY = 'telegram_expense_manager.analytic_tag_liquidity'
TAG_PAYABLE = 'telegram_expense_manager.analytic_tag_payable'
TAG_RECEIVABLE = 'telegram_expense_manager.analytic_tag_receivable'

ACCOUNT_LIQUIDITY = 'telegram_expense_manager.account_liquidity'
ACCOUNT_PAYABLE = 'telegram_expense_manager.account_payable'
ACCOUNT_RECEIVABLE = 'telegram_expense_manager.account_receivable'

JOURNAL_LIQUIDITY = 'telegram_expense_manager.journal_liquidity'
JOURNAL_PAYABLE = 'telegram_expense_manager.journal_payable'
JOURNAL_RECEIVABLE = 'telegram_expense_manager.journal_receivable'


class Partner(models.Model):

    _inherit = 'res.partner'

    @api.multi
    def em_browse_record(self, record_id):
        record = self.env['account.move'].sudo().browse(record_id)
        self.em_check_access(record)
        return record

    @api.multi
    def em_check_access(self, record, raise_on_error=True):
        self.ensure_one()
        if not record.partner_id or record.partner_id != self:
            if raise_on_error:
                raise AccessError(_("You don't have access to this record"))
            return False
        return True

    @api.multi
    def em_default_analytic_payable(self):
        return self.env['account.analytic.account']

    @api.multi
    def em_default_analytic_liquidity(self):
        return self.env['account.analytic.account']

    @api.multi
    def em_create_analytic_liquidity(self, name):
        return self._em_create_analytic(
            name, self.env.ref(TAG_LIQUIDITY))

    @api.multi
    def em_create_analytic_payable(self, name):
        return self._em_create_analytic(
            name, self.env.ref(TAG_PAYABLE))

    @api.multi
    def _em_create_analytic(self, name, tag):
        analytic = self.env['account.analytic.account'].sudo().create({
            'name': name,
            'partner_id': self.id,
            'tag_ids': [(4, tag.id, None)],
        })
        return analytic

    @api.multi
    def em_add_new_record(self, text, amount, currency):
        liquidity = self.env.ref(ACCOUNT_LIQUIDITY)
        payable = self.env.ref(ACCOUNT_PAYABLE)
        analytic_payable = self.em_default_analytic_payable()
        analytic_liquidity = self.em_default_analytic_liquidity()
        journal = self.env.ref(JOURNAL_PAYABLE)

        amount = float(amount.replace(',', '.'))

        common = {
            'partner_id': self.id,
            'name': text or 'unknown',
        }
        # move from source (e.g. wallet)
        credit = common.copy()
        credit.update({
            'account_id': liquidity.id,
            'credit': amount,
            'analytic_account_id': analytic_liquidity.id,
        })
        # move to target (e.g. cashier)
        debit = common.copy()
        debit.update({
            'account_id': payable.id,
            'debit': amount,
            'analytic_account_id': analytic_payable.id,
        })
        record = self.env['account.move'].create({
            'narration': text,
            'journal_id': journal.id,
            'line_ids': [
                (0, 0, debit),
                (0, 0, credit),
            ]
        })
        return record


class AccountMove(models.Model):

    _inherit = 'account.move'

    @api.multi
    def em_update_analytic_liquidity(self, analytic_liquidity):
        return self._em_update_analytic(
            analytic_liquidity, TYPE_LIQUIDITY)

    @api.multi
    def em_update_analytic_payable(self, analytic_payable):
        return self._em_update_analytic(
            analytic_payable, TYPE_PAYABLE)

    @api.multi
    def _em_update_analytic(self, new_analytic, user_type_ref):
        user_type = self.env.ref(user_type_ref)
        for line in self.line_ids:
            if line.account_id.user_type_id == user_type:
                line.analytic_account_id = new_analytic
                return True
        return False

    @api.multi
    def em_get_analytic_liquidity(self):
        return self._em_get_analytic(TYPE_LIQUIDITY)

    @api.multi
    def em_get_analytic_payable(self):
        return self._em_get_analytic(TYPE_PAYABLE)

    @api.multi
    def _em_get_analytic(self, user_type_ref):
        user_type = self.env.ref(user_type_ref)
        for line in self.line_ids:
            if line.account_id.user_type_id == user_type:
                return line.analytic_account_id
        return False
