# -*- coding: utf-8 -*-
from odoo import models, api, fields
from odoo.exceptions import AccessError
from odoo.tools.translate import _
from odoo.tools.safe_eval import safe_eval

ASK_PARTNER_NAME = 'ask_partner_name'
ASK_NOTE = 'ask_note'
ASK_PHONE = 'ask_phone'
ASK_MOBILE = 'ask_mobile'
ASK_EMAIL = 'ask_email'

class TelegramCommand(models.Model):

    _inherit = 'telegram.command'


class Partner(models.Model):

    _inherit = 'res.partner'

    @api.multi
    def gd_update_name(self, text):
        self.sudo().name = text
#        self.write({'name': text})

    @api.multi
    def gd_update_note(self, text):
        self.sudo().note = text
#        self.write({'note': text})

    @api.multi
    def gd_update_phone(self, text):
        self.sudo().phone = text
#        self.write({'name': text})

    @api.multi
    def gd_update_mobile(self, text):
        self.sudo().mobile = text

    @api.multi
    def gd_update_email(self, text):
        self.sudo().email = text

    @api.multi
    def gd_check_access(self, record, raise_on_error=True):
        self.ensure_one()
        if not record.id or record.id != self:
            if raise_on_error:
                raise AccessError(_("You don't have access to this record"))
            return False
        return True

    @api.multi
    def gd_browse_record(self, record_id):
        record = self.env['res.partner'].sudo().browse(record_id)
        #self.gd_check_access(record)
        return record


    def _gd_ask(self, options, command, record, action):
        data = {
            'action': action,
            'record_id': record.id if record else 0,
        }
        options['handle_reply'] = {
            'replies': {},
            'custom_reply': data,
        }


    def gd_ask_partner_name(self, options, command, record):
        self._gd_ask(options, command, record, ASK_PARTNER_NAME)

    def gd_ask_note(self, options, command, record):
        self._gd_ask(options, command, record, ASK_NOTE)

    def gd_ask_phone(self, options, command, record):
        self._gd_ask(options, command, record, ASK_PHONE)

    def gd_ask_mobile(self, options, command, record):
        self._gd_ask(options, command, record, ASK_MOBILE)

    def gd_ask_email(self, options, command, record):
        self._gd_ask(options, command, record, ASK_EMAIL)

    @api.multi
    def gd_handle_callback_data(self, callback_data, raw_text, add_record=None):
        record = self.gd_browse_record(callback_data.get('record_id')) \
            if callback_data.get('record_id') else None
        error = None
        #import pdb; pdb.set_trace()
        if callback_data.get('action') == ASK_PARTNER_NAME:
            if not record:
                record = self.env['res.partner'].sudo().create({'name': raw_text})
                if add_record:
                    record.rs_telegram_id=add_record
                    session=self.env['telegram.session'].sudo().search([('chat_ID','=',add_record)])
                    session.partner_id=record.id
            else:
                record.gd_update_partner_name(raw_text)
        elif callback_data.get('action') == ASK_NOTE:
            record.gd_update_note(raw_text)
        elif callback_data.get('action') == ASK_PHONE:
            record.gd_update_phone(raw_text)
        elif callback_data.get('action') == ASK_MOBILE:
            record.gd_update_mobile(raw_text)
        elif callback_data.get('action') == ASK_EMAIL:
            record.gd_update_email(raw_text)

        return record, error
