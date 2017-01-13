# -*- coding: utf-8 -*-
from odoo import models, api, fields
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

TAG2TYPE = {
    TAG_LIQUIDITY: TYPE_LIQUIDITY,
    TAG_PAYABLE: TYPE_PAYABLE,
    TAG_RECEIVABLE: TYPE_RECEIVABLE,
}


class TelegramCommand(models.Model):

    _inherit = 'telegram.command'

    TAG_LIQUIDITY = TAG_LIQUIDITY
    TAG_PAYABLE = TAG_PAYABLE
    TAG_RECEIVABLE = TAG_RECEIVABLE

class Partner(models.Model):

    _inherit = 'res.partner'

    @api.multi
    def em_browse_record(self, record_id):
        record = self.env['account.move'].sudo().browse(record_id)
        self.em_check_access(record)
        return record

    @api.model
    def em_browse_line(self, line_id):
        line = self.env['account.move.line'].sudo().browse(line_id)
        record = line.move_id
        self.em_check_access(record)
        return line

    @api.multi
    def em_browse_analytic(self, analytic_id):
        self.ensure_one()
        analytic = self.env['account.analytic.account'].sudo().browse(analytic_id)
        if analytic.partner_id != self:
            raise AccessError(_("You don't have access to this analytic"))
        return analytic

    @api.multi
    def em_keyboard_analytics(self, options, command, record, tag):
        data = {
            'tag': tag,
            'record_id': record.id,
        }
        buttons = [
            {'text': an.name,
             'callback_data': dict(
                 data.items() +
                 [('analytic_id', an.id)]
             )
             } for an in self._em_all_analytics(tag)
        ]
        command.keyboard_buttons(options, buttons, row_width=1)
        options['handle_reply']['custom_reply'] = data
        return buttons

    @api.multi
    def em_handle_callback_data(self, callback_data, raw_text):
        record = self.em_browse_record(callback_data.get('record_id'))
        tag = callback_data.get('tag')
        if callback_data.get('analytic_id'):
            analytic_liquidity = self.em_browse_analytic(callback_data('analytic_id'))
        else:
            analytic_liquidity = self._em_create_analytic(raw_text, tag)
        record._em_update_analytic(analytic_liquidity, TAG2TYPE[tag])
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
    def em_all_analytics_liquidity(self, tag):
        return self._em_all_analytics(TAG_LIQUIDITY)

    @api.multi
    def em_all_analytics_payable(self, tag):
        return self._em_all_analytics(TAG_PAYABLE)

    @api.multi
    def _em_all_analytics(self, tag, count=False):
        self.ensure_one()
        if not tag:
            return []
        tag = self.env.ref(tag)
        domain = [('partner_id', '=', self.id)]
        domain += [('tag_ids', '=', tag.id)]
        return self.env['account.analytic.account'].search(domain, count=count)

    @api.multi
    def em_default_analytic_payable(self, text):
        return self._em_guess_analytic(text, ACCOUNT_LIQUIDITY)

    @api.multi
    def em_default_analytic_liquidity(self, text):
        analytic = self._em_guess_analytic(text, ACCOUNT_LIQUIDITY)
        if analytic:
            return analytic
        count = self._em_all_analytics(TAG_LIQUIDITY, count=True)
        if not count:
            analytic = self.em_create_analytic_liquidity(_('Money for common expenses'))
            return analytic
        elif count == 1:
            return self._em_all_analytics(TAG_LIQUIDITY)
        else:
            # More than one analytics. Let user to choose himself
            return self.env['account.analytic.account']

    def _em_guess_analytic(self, text, tag):
        # TODO
        return self.env['account.analytic.account']

    @api.multi
    def em_create_analytic_liquidity(self, name):
        return self._em_create_analytic(name, TAG_LIQUIDITY)

    @api.multi
    def em_create_analytic_payable(self, name):
        return self._em_create_analytic(name, TAG_PAYABLE)

    @api.multi
    def _em_create_analytic(self, name, tag):
        tag = self.env.ref(tag)
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
        analytic_payable = self.em_default_analytic_payable(text)
        analytic_liquidity = analytic_payable.liquidity_id \
            or self.em_default_analytic_liquidity(text)
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
    def em_update_amount(self, amount):
        self.ensure_one()
        update_lines = []
        for line in self.line_ids:
            if line.is_from:
                update_lines.append((1, line.id, {'credit': amount}))
            elif line.is_to:
                update_lines.append((1, line.id, {'debit': amount}))
        self.write({'line_ids': update_lines})

    @api.multi
    def em_update_note(self, text):
        self.narration = text
        self.line_ids.write({'name': text})

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

    @api.multi
    def em_lines(self):
        res = {
            'from': {},
            'to': {}
        }
        for line in self.line_ids:
            key = 'from' if line.is_from else 'to'
            res[key] = {
                'analytic': line.analytic_account_id.name,
                'id': line.id,
            }
        return res


class AccountMoveLine(models.Model):

    _inherit = 'account.move.line'

    is_from = fields.Boolean(compute='_compute_em_type')
    is_to = fields.Boolean(compute='_compute_em_type')

    def _compute_em_type(self):
        for r in self:
            r.is_from = r.credit or r.account_id == self.env.ref(ACCOUNT_RECEIVABLE)
            r.is_to = r.debit or r.account_id == self.env.ref(ACCOUNT_PAYABLE)

    @api.multi
    def _em_analytic_tag(self):
        self.ensure_one()
        return {
            self.env.ref(ACCOUNT_RECEIVABLE).id: TAG_RECEIVABLE,
            self.env.ref(ACCOUNT_PAYABLE).id: TAG_PAYABLE,
            self.env.ref(ACCOUNT_LIQUIDITY).id: TAG_LIQUIDITY,
        }.get(self.account_id.id)

    @api.multi
    def em_all_analytics(self):
        self.ensure_one()
        partner = self.partner_id
        assert partner, _("Record line doesn't have partner value")
        return partner._em_all_analytics(self._em_analytic_tag())

    def em_create_analytic(self, name):
        self.ensure_one()
        partner = self.partner_id
        assert partner, _("Record line doesn't have partner value")
        tag = self._em_analytic_tag()
        return partner._em_create_analytic(name, tag)

    def em_update_analytic(self, analytic):
        self.analytic_account_id = analytic
