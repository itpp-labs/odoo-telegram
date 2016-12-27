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


class TelegramCommand(models.Model):

    _inherit = 'telegram.command'

    @api.model
    def em_check_access(self, partner, record, raise_on_error=True):
        if record.partner_id != partner:
            if raise_on_error:
                raise AccessError(_("You don't have access to this record"))
            return False
        return True

    @api.model
    def em_default_analytic_payable(self, partner):
        return self.env['account.analytic.account']

    @api.model
    def em_default_analytic_liquidity(self, partner):
        return self.env['account.analytic.account']

    @api.model
    def em_create_analytic_liquidity(self, partner, name):
        return self._em_create_analytic(
            partner, name, self.env.ref(TAG_LIQUIDITY))

    @api.model
    def em_create_analytic_payable(self, partner, name):
        return self._em_create_analytic(
            partner, name, self.env.ref(TAG_PAYABLE))

    @api.model
    def _em_create_analytic(self, partner, name, tag):
        analytic = self.env['account.analytic.account'].sudo().create({
            'name': name,
            'partner_id': partner.id,
            'tag_ids': [(4, tag.id, None)],
        })
        return analytic

    @api.model
    def em_update_analytic_liquidity(self, partner, record, analytic_liquidity):
        return self._em_update_analytic(
            partner, record,
            analytic_liquidity, TYPE_LIQUIDITY)

    @api.model
    def em_update_analytic_payable(self, partner, record, analytic_payable):
        return self._em_update_analytic(
            partner, record,
            analytic_payable, TYPE_PAYABLE)

    @api.model
    def _em_update_analytic(self, partner, record, new_analytic, user_type_ref):
        self.em_check_access(partner, record)
        user_type = self.env.ref(user_type_ref)
        for line in record.line_ids:
            if line.account_id.user_type_id == user_type:
                line.analytic_account_id = new_analytic
                return True
        return False

    @api.model
    def em_record2analytic_liquidity(self, partner, record):
        return self._em_record2analytic(
            partner, record,
            TYPE_LIQUIDITY)

    @api.model
    def em_record2analytic_payable(self, partner, record):
        return self._em_record2analytic(
            partner, record,
            TYPE_PAYABLE)

    @api.model
    def _em_record2analytic(self, partner, record, user_type_ref):
        self.em_check_access(partner, record)
        user_type = self.env.ref(user_type_ref)
        for line in record.line_ids:
            if line.account_id.user_type_id == user_type:
                return line.analytic_account_id
        return False

    @api.model
    def em_add_new_record(self, partner, text, amount, currency):
        liquidity = self.env.ref(ACCOUNT_LIQUIDITY)
        payable = self.env.ref(ACCOUNT_PAYABLE)
        analytic_payable = self.em_default_analytic_payable(partner)
        analytic_liquidity = self.em_default_analytic_liquidity(partner)
        journal = self.env.ref(JOURNAL_PAYABLE)

        amount = float(amount.replace(',', '.'))

        common = {
            'partner_id': partner.id,
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
            'journal_id': journal.id,
            'line_ids': [
                (0, 0, debit),
                (0, 0, credit),
            ]
        })
        return record
