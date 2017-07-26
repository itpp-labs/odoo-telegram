# -*- coding: utf-8 -*-
from odoo import models, api, fields
from odoo.exceptions import AccessError
from odoo.tools.translate import _
from odoo.tools.safe_eval import safe_eval

TYPE_LIQUIDITY = 'account.data_account_type_liquidity'
TYPE_PAYABLE = 'account.data_account_type_payable'
TYPE_RECEIVABLE = 'account.data_account_type_receivable'

TAG_LIQUIDITY = 'telegram_expense_manager.analytic_tag_liquidity'
TAG_PAYABLE = 'telegram_expense_manager.analytic_tag_payable'
TAG_RECEIVABLE = 'telegram_expense_manager.analytic_tag_receivable'

ACCOUNT_LIQUIDITY = 'telegram_expense_manager.account_liquidity'
ACCOUNT_PAYABLE = 'telegram_expense_manager.account_payable'
ACCOUNT_RECEIVABLE = 'telegram_expense_manager.account_receivable'

JOURNAL_TRANSFER = 'telegram_expense_manager.journal_transfer'
JOURNAL_PAYABLE = 'telegram_expense_manager.journal_payable'
JOURNAL_RECEIVABLE = 'telegram_expense_manager.journal_receivable'

TAG2TYPE = {
    TAG_LIQUIDITY: TYPE_LIQUIDITY,
    TAG_PAYABLE: TYPE_PAYABLE,
    TAG_RECEIVABLE: TYPE_RECEIVABLE,
}


ASK_AMOUNT = 'ask_amount'
ASK_NOTE = 'ask_note'
ASK_ANALYTIC_TAG = 'ask_analytic_tag'
ASK_ANALYTIC = 'ask_analytic'
ASK_PERIODICITY_TYPE = 'ask_periodicity_type'
ASK_PERIODICITY_AMOUNT = 'ask_periodicity_AMOUNT'
ASK_NOTIFY_ON_TRANSFER = 'ask_notify_on_transfer'


PERIODICITY_OPTIONS = {
    'day': {
        1: _("Every day"),
        2: _("Every 2 days"),
        3: _("Every 3 days"),
        4: _("Every 4 days"),
        5: _("Every 5 days"),
        6: _("Every 6 days"),
    },
    'week': {
        1: _("Every week"),
        2: _("Every 2 weeks"),
        3: _("Every 3 weeks"),
    },
    'month': {
        1: _("Every month"),
        2: _("Every 2 months"),
        3: _("Every 3 months"),
        6: _("Every 6 months"),
        12: _("Every 12 months"),
    },
}


class TelegramCommand(models.Model):

    _inherit = 'telegram.command'

    TAG_LIQUIDITY = TAG_LIQUIDITY
    TAG_PAYABLE = TAG_PAYABLE
    TAG_RECEIVABLE = TAG_RECEIVABLE

    JOURNAL_TRANSFER = JOURNAL_TRANSFER
    JOURNAL_PAYABLE = JOURNAL_PAYABLE
    JOURNAL_RECEIVABLE = JOURNAL_RECEIVABLE


class Partner(models.Model):

    _inherit = 'res.partner'

    @api.multi
    def em_browse_record(self, record_id):
        record = self.env['account.move'].sudo().browse(record_id)
        self.em_check_access(record)
        return record

    def em_browse_schedule(self, record_id):
        record = self.env['account.schedule'].sudo().browse(record_id)
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
    def em_ask_analytic(self, options, command, record, tag_ref=None, tag_id=None, is_from=None, is_to=None):
        if not tag_ref:
            tag_ref = self._tag2ref()[tag_id]

        data = {
            'action': ASK_ANALYTIC,
            'tag_ref': tag_ref,
            'record_id': record.id,
        }
        if is_from or is_to:
            data['transfer'] = 'from' if is_from else 'to'

        buttons = [
            {'text': an.name,
             'callback_data': dict(
                 data.items() +
                 [('analytic_id', an.id)]
             )
             } for an in self._em_all_analytics(tag_ref=tag_ref, tag_id=tag_id)
        ]
        command.keyboard_buttons(options, buttons, row_width=1)
        options['handle_reply']['custom_reply'] = data
        return buttons

    def em_ask_amount(self, options, command, record):
        self._em_ask(options, command, record, ASK_AMOUNT)

    def em_ask_note(self, options, command, record):
        self._em_ask(options, command, record, ASK_NOTE)

    def em_ask_analytic_tag(self, options, command, record, is_from=None, is_to=None):
        data = {
            'action': ASK_ANALYTIC_TAG,
            'record_id': record.id,
        }
        if is_from or is_to:
            data['transfer'] = 'from' if is_from else 'to'

        TAG2STRING = {
            TAG_LIQUIDITY: _("Account"),
            TAG_PAYABLE: _("Expense"),
            TAG_RECEIVABLE: _("Income"),
        }
        if is_from:
            del TAG2STRING[TAG_PAYABLE]
        if is_to:
            del TAG2STRING[TAG_RECEIVABLE]

        buttons = [
            {'text': name,
             'callback_data': dict(
                 data.items() +
                 [('tag_ref', tag_ref)]
             )
             } for tag_ref, name in TAG2STRING.items()
        ]
        command.keyboard_buttons(options, buttons, row_width=1)
        options['handle_reply']['custom_reply'] = data
        return buttons

    def em_ask_periodicity_type(self, options, command, record):
        data = {
            'action': ASK_PERIODICITY_TYPE,
            'record_id': record.id,
        }

        buttons = [
            {'text': name,
             'callback_data': dict(
                 data.items() +
                 [('periodicity_type', code)]
             )
             } for code, name in self.env['account.schedule']._fields['periodicity_type'].selection
        ]
        command.keyboard_buttons(options, buttons, row_width=1)
        return buttons

    def em_ask_periodicity_amount(self, options, command, record):
        data = {
            'action': ASK_PERIODICITY_AMOUNT,
            'record_id': record.id,
        }

        buttons = [
            {'text': name,
             'callback_data': dict(
                 data.items() +
                 [('periodicity_amount', value)]
             )
             } for value, name in PERIODICITY_OPTIONS[record.periodicity_type].items()
        ]
        command.keyboard_buttons(options, buttons, row_width=1)
        options['handle_reply']['custom_reply'] = data
        return buttons

    def em_ask_notify_on_transfer(self, options, command, schedule):
        data = {
            'action': ASK_NOTIFY_ON_TRANSFER,
            'record_id': schedule.id,
        }

        buttons = [
            {'text': name,
             'callback_data': dict(
                 data.items() +
                 [('notify', code)]
             )
             } for code, name in self.env['account.schedule']._fields['notify'].selection
        ]
        command.keyboard_buttons(options, buttons, row_width=1)
        return buttons

    def _em_ask(self, options, command, record, action):
        data = {
            'action': action,
            'record_id': record.id if record else 0,
        }
        options['handle_reply'] = {
            'replies': {},
            'custom_reply': data,
        }

    @api.multi
    def em_handle_callback_data(self, callback_data, raw_text, add_record=None):
        record = self.em_browse_record(callback_data.get('record_id')) \
            if callback_data.get('record_id') else None
        error = None

        if callback_data.get('action') == ASK_AMOUNT:
            if not record:
                record = add_record('', raw_text)
            else:
                record.em_update_amount(raw_text)
        elif callback_data.get('action') == ASK_NOTE:
            record.em_update_note(raw_text)
        elif callback_data.get('action') == ASK_ANALYTIC:
            tag = callback_data.get('tag_ref')
            if callback_data.get('analytic_id'):
                analytic_liquidity = self.em_browse_analytic(callback_data.get('analytic_id'))
            else:
                analytic_liquidity = self._em_create_analytic(raw_text, tag)
            record._em_update_analytic(analytic_liquidity, TAG2TYPE[tag], callback_data.get('transfer'))
        return record, error

    @api.multi
    def em_handle_callback_data_schedule(self, callback_data, raw_text):
        record = self.em_browse_schedule(callback_data.get('record_id')) \
            if callback_data.get('record_id') else None
        error = None

        if callback_data.get('action') == ASK_AMOUNT:
            if not record:
                user_id = self.env.user.id
                record = self.env['account.schedule'].sudo().create({'user_id': user_id})
            record.amount = raw_text
        elif callback_data.get('action') == ASK_NOTE:
            record.name = raw_text
        elif callback_data.get('action') == ASK_ANALYTIC_TAG:
            tag = callback_data.get('tag_ref')
            tag = self.env.ref(tag)
            if callback_data.get('transfer') == 'from':
                record.from_tag_id = tag
            else:
                record.to_tag_id = tag
        elif callback_data.get('action') == ASK_ANALYTIC:
            tag = callback_data.get('tag_ref')
            if callback_data.get('analytic_id'):
                analytic = self.em_browse_analytic(callback_data.get('analytic_id'))
            else:
                analytic = self._em_create_analytic(raw_text, tag)
            if callback_data.get('transfer') == 'from':
                record.from_analytic_id = analytic
            else:
                record.to_analytic_id = analytic
        elif callback_data.get('action') == ASK_PERIODICITY_TYPE:
            record.periodicity_type = callback_data.get('periodicity_type')
        elif callback_data.get('action') == ASK_PERIODICITY_AMOUNT:
            record.periodicity_amount = callback_data.get('periodicity_amount')
        elif callback_data.get('action') == ASK_NOTIFY_ON_TRANSFER:
            record.notify = callback_data.get('notify')
        return record, error

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
    def _em_all_analytics(self, tag_ref, tag_id=None, count=False):
        self.ensure_one()
        if tag_ref:
            tag_id = self.env.ref(tag_ref).id
        if not tag_id:
            return []
        domain = [('partner_id', '=', self.id)]
        domain += [('tag_ids', '=', tag_id)]
        return self.env['account.analytic.account'].search(domain, count=count)

    @api.multi
    def em_default_analytic_payable(self, text):
        return self._em_guess_analytic(text, ACCOUNT_PAYABLE)

    @api.multi
    def em_default_analytic_liquidity(self, text):
        analytic = self._em_guess_analytic(text, ACCOUNT_LIQUIDITY)
        if analytic:
            return analytic
        count = self._em_all_analytics(TAG_LIQUIDITY, count=True)
        if not count:
            analytic = self.em_create_analytic_liquidity(_('General account'))
            return analytic
        elif count == 1:
            return self._em_all_analytics(TAG_LIQUIDITY)
        else:
            # More than one analytics. Let user to choose himself
            return self.env['account.analytic.account']

    @api.multi
    def _em_guess_analytic(self, text, account_ref):
        account = self.env.ref(account_ref)
        line = self.env['account.move.line'].search([
            ('partner_id', '=', self.id),
            ('name', '=ilike', text),
            ('account_id', '=', account.id)
        ], order='id DESC', limit=1)
        if not line:
            return self.env['account.analytic.account']
        return line.analytic_account_id

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
    def em_add_expense_record(self, text, amount, currency=None):
        amount = safe_eval(amount)
        account_liquidity = self.env.ref(ACCOUNT_LIQUIDITY)
        account_payable = self.env.ref(ACCOUNT_PAYABLE)
        analytic_payable = self.em_default_analytic_payable(text)
        analytic_liquidity = analytic_payable.liquidity_id \
            or self.em_default_analytic_liquidity(text)

        from_data = {
            'account_id': account_liquidity.id,
            'analytic_account_id': analytic_liquidity.id,
        }
        to_data = {
            'account_id': account_payable.id,
            'analytic_account_id': analytic_payable.id,
        }
        return self._em_add_record(text, amount, currency,
                                   JOURNAL_PAYABLE, from_data, to_data)

    @api.multi
    def em_add_income_record(self, text, amount, currency=None):
        account_liquidity = self.env.ref(ACCOUNT_LIQUIDITY)
        account_receivable = self.env.ref(ACCOUNT_RECEIVABLE)

        from_data = {
            'account_id': account_receivable.id,
        }
        to_data = {
            'account_id': account_liquidity.id,
        }
        return self._em_add_record(text, amount, currency,
                                   JOURNAL_RECEIVABLE, from_data, to_data)

    @api.multi
    def em_add_transfer_record(self, text, amount, currency=None):
        account_liquidity = self.env.ref(ACCOUNT_LIQUIDITY)

        from_data = {
            'account_id': account_liquidity.id,
        }
        to_data = {
            'account_id': account_liquidity.id,
        }
        return self._em_add_record(text, amount, currency,
                                   JOURNAL_TRANSFER, from_data, to_data)

    def _tag2ref(self):
        return {
            self.env.ref(self.env['telegram.command'].TAG_RECEIVABLE).id: TAG_RECEIVABLE,
            self.env.ref(self.env['telegram.command'].TAG_LIQUIDITY).id: TAG_LIQUIDITY,
            self.env.ref(self.env['telegram.command'].TAG_PAYABLE).id: TAG_PAYABLE,
        }

    @api.multi
    def em_add_record_from_schedule(self, schedule):
        if not all([
                schedule.from_tag_id,
                schedule.to_tag_id,
                schedule.from_analytic_id,
                schedule.to_analytic_id,
                schedule.amount,
        ]):
            return None
        from_ref = self._tag2ref()[schedule.from_tag_id.id]
        to_ref = self._tag2ref()[schedule.to_tag_id.id]
        if from_ref == TAG_RECEIVABLE:
            account_from = self.env.ref(ACCOUNT_RECEIVABLE)
            account_to = self.env.ref(ACCOUNT_LIQUIDITY)
            journal = JOURNAL_RECEIVABLE
        elif to_ref == TAG_PAYABLE:
            account_from = self.env.ref(ACCOUNT_LIQUIDITY)
            account_to = self.env.ref(ACCOUNT_PAYABLE)
            journal = JOURNAL_PAYABLE
        else:
            account_from = self.env.ref(ACCOUNT_LIQUIDITY)
            account_to = self.env.ref(ACCOUNT_LIQUIDITY)
            journal = JOURNAL_TRANSFER

        from_data = {
            'account_id': account_from.id,
            'analytic_account_id': schedule.from_analytic_id.id,
        }
        to_data = {
            'account_id': account_to.id,
            'analytic_account_id': schedule.to_analytic_id.id,
        }

        text = schedule.name or _('undefined')
        currency = None
        amount = schedule.amount

        record = self._em_add_record(text, amount, currency,
                                     journal, from_data, to_data)
        record.schedule_id = schedule
        return record

    def _em_add_record(self,
                       text, amount, currency,
                       journal_ref, from_data, to_data):

        journal = self.env.ref(journal_ref)

        common = {
            'partner_id': self.id,
            'name': text or 'unknown',
        }
        if isinstance(amount, basestring):
            amount = float(amount.replace(',', '.'))

        # move from source (e.g. wallet)
        credit = common.copy()
        credit.update(from_data)
        credit.update({
            'credit': amount,
        })
        # move to target (e.g. cashier)
        debit = common.copy()
        debit.update(to_data)
        debit.update({
            'debit': amount,
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
    """Class for ``record``"""
    _inherit = 'account.move'

    schedule_id = fields.Many2one('account.schedule', help='Schedule which created this record')

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
    def _em_update_analytic(self, new_analytic, user_type_ref=None, transfer=None):
        user_type = self.env.ref(user_type_ref)
        for line in self.line_ids:
            update = False
            if transfer:
                if line.is_from and transfer == 'from':
                    update = True

                if line.is_to and transfer == 'to':
                    update = True

            elif line.account_id.user_type_id == user_type:
                update = True

            if update:
                line.analytic_account_id = new_analytic
                return True
        return False

    @api.multi
    def em_get_analytic_liquidity(self):
        return self._em_get_analytic(TYPE_LIQUIDITY)

    @api.multi
    def em_get_analytic_payable(self):
        return self._em_get_analytic(TYPE_PAYABLE)

    def em_get_analytic_receivable(self):
        return self._em_get_analytic(TYPE_RECEIVABLE)

    @api.multi
    def _em_get_analytic(self, user_type_ref):
        user_type = self.env.ref(user_type_ref)
        for line in self.line_ids:
            if line.account_id.user_type_id == user_type:
                return line.analytic_account_id
        return False

    @api.multi
    def em_get_analytic_from(self):
        for line in self.line_ids:
            if line.is_from:
                return line.analytic_account_id
        return False

    @api.multi
    def em_get_analytic_to(self):
        for line in self.line_ids:
            if line.is_to:
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
