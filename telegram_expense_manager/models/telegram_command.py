from odoo import models, api


class TelegramCommand(models.Model):

    _inherit = 'telegram.command'

    @api.model
    def em_get_liquidity_account(self):
        user_type = self.env.ref('account.data_account_type_liquidity')
        account = self.env['account.account'].search([('user_type_id', '=', user_type.id)])
        return account and account[0]

    @api.model
    def em_get_payable_account(self):
        return self._em_get_account('payable')

    @api.model
    def em_get_receivable_account(self):
        return self._em_get_account('receivable')

    @api.model
    def _em_get_account(self, internal_type):
        res = self.env['account.account'].search([('internal_type', '=', internal_type)])
        return res and res[0]

    @api.model
    def em_default_analytic_payable(self, partner):
        return self.env['account.analytic.account']

    @api.model
    def em_default_analytic_liquidity(self, partner):
        return self.env['account.analytic.account']


    @api.model
    def em_add_new_record(self, partner, text, amount, currency):
        liquidity = self.env.ref('telegram_expense_manager.account_liquidity')
        payable = self.env.ref('telegram_expense_manager.account_payable')
        analytic_payable = self.em_default_analytic_payable(partner)
        analytic_liquidity = self.em_default_analytic_liquidity(partner)
        journal = self.env.ref('telegram_expense_manager.tele_journal')

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
