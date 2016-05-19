# -*- coding:utf-8 -*-

from openerp import api, fields, models
import base64
import cStringIO
from datetime import datetime


class ExportInvoice1C(models.Model):
    _name = "account.invoice.export.1c"
    _description = "Exports invoice for 1c client bank"
    mdata = fields.Binary()
    invisible = fields.Boolean(default=False)
    line_ids = fields.Many2many('account.invoice')
    bank_acc = fields.Many2one('account.journal', domain=[('type', '=', 'bank')])
    fname = fields.Char()

    @api.model
    def default_get(self, fields):
        record_ids = self.env.context.get('active_ids')
        res = {'line_ids': [(6, 0, record_ids)]}
        return res

    @api.multi
    def open_website_url(self):
        self.make_file()
        self.fname = 'to_client_bank_'+str(datetime.now().strftime("%d-%m-%Y_%H-%M-%S"))+'.txt'
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.invoice.export.1c',
            'view_mode': 'form',
            'view_type': 'form',
            'res_id': self.id,
            'views': [(False, 'form')],
            'target': 'new',
        }

    @api.multi
    def make_file(self):
        context = dict(self._context or {})
        active_ids = context.get('active_ids', []) or []
        f = cStringIO.StringIO()
        # Заголовок файла
        f.write('1CClientBankExchange\n')
        # Общие сведения
        f.write('ВерсияФормата=1.01\n')
        f.write('Кодировка=Windows\n')
        f.write('Отправитель=Odoo9\n')
        f.write('Получатель=Клиент-Банк\n')
        f.write('ДатаСоздания=' + datetime.now().strftime("%d.%m.%Y") + '\n')
        f.write('ВремяСоздания='+ datetime.now().strftime("%H:%M:%S") + '\n')
        # Сведения об условиях отбора передаваемых данных
        f.write('ДатаНачала=' + 'дата начала отбора' + '\n')
        f.write('ДатаКонца=' + 'дата конца отбора' + '\n')
        f.write('РасчСчет=' + '123456789' + '\n')
        # Секция передачи остатков по расчетному счету - НЕ НУЖНА ДЛЯ ВЫГРУЗКИ
        # f.write('СекцияРасчСчет' + '\n')
        # f.write('ДатаНачала=' + '01.01.2000' + '\n')
        # f.write('ДатаКонца=' + '01.01.2000' + '\n')
        # f.write('РасчСчет=' + '123456789' + '\n')
        # f.write('НачальныйОстаток=' + '0' + '\n')
        # f.write('ВсегоПоступило=' + '0' + '\n')
        # f.write('ВсегоСписано=' + '0' + '\n')
        # f.write('КонечныйОстаток=' + '0' + '\n')
        # f.write('КонецРасчСчет' + '\n')

        for rec in self.env['account.invoice'].browse(active_ids):
            # Секция платежного документа
            inv_type = ''
            if rec.type == 'out_invoice':
                inv_type = 'Платежное поручение'
            elif rec.type == 'in_invoice':
                # inv_type = 'Платежное требование'
                # Не выгружаем требования
                continue
            elif rec.type == 'out_refund':
                inv_type = 'Возврат покупателю'
            elif rec.type == 'in_refund':
                # inv_type = 'Возврат поставщику'
                # Не выгружаем
                continue
            # Шапка платежного документа
            f.write('СекцияДокумент=' + inv_type + '\n')
            try: f.write('Номер=' + str(rec.number) + '\n')
            except: a=1
            f.write('Дата=' + str(rec.date_invoice) + '\n')
            f.write('Сумма=' + str(rec.amount_total_signed) + '\n')
            # Реквизиты плательщика
            bank = self.bank_acc.bank_id
            company = rec.company_id.partner_id
            adr = bank.city + ', ' + bank.street + ' ' + bank.street2
            f.write('ПлательщикСчет=' + str(self.bank_acc.bank_acc_number) + '\n')
            f.write('Плательщик=' + str(company.name) + '\n')
            f.write('ПлательщикИНН=' + str(company.inn) + '\n')
            f.write('ПлательщикКПП=' + str(company.kpp) + '\n')
            f.write('ПлательщикРасчСчет=' + str(self.bank_acc.bank_acc_number) + '\n')
            f.write('ПлательщикБанк1=' + str(bank.name) + '\n')
            f.write('ПлательщикБанк2=' + adr.encode('utf-8') + '\n')
            f.write('ПлательщикБИК=' + str(bank.bic) + '\n')
            f.write('ПлательщикКорсчет=' + str(bank.acc_corr) + '\n')
            # Реквизиты банка получателя (поставщика)
            f.write('ПолучательСчет=' + str('0') + '\n')
            f.write('ПолучательИНН=' + str('0') + '\n')
            f.write('ПолучательКПП=' + str('0') + '\n')
            f.write('Получатель=' + str('0') + '\n')
            f.write('Получатель1=' + str('0') + '\n')
            f.write('ПолучательРасчСчет=' + str('0') + '\n')
            f.write('ПолучательБанк1=' + str('0') + '\n')
            f.write('ПолучательБанк2=' + str('0') + '\n')
            f.write('ПолучательБИК=' + str('0') + '\n')
            f.write('ПолучательКорсчет=' + str('0') + '\n')
            # Реквизиты платежа
            f.write('ВидПлатежа=Электронно\n')
            f.write('ВидОплаты=01\n')
            f.write('Очередность=6 \n')
            f.write('НазначениеПлатежа=' + str('0') + '\n')
            # В формате не предусмотрена построчная аналитика. Частично можно сделать так:
            lines = self.env['account.invoice.line'].search([('invoice_id','=',rec.id)])
            cnt = 0
            for line in lines:
                f.write('НазначениеПлатежа=' + line.name.encode('utf-8'))
                f.write('Название ' + line.name.encode('utf-8') + ' ')
                f.write('Количество ' + str(line.quantity) + ' ')
                f.write('Цена ' + str(line.price_unit) + '\n')
                cnt += 1
        out = base64.encodestring(f.getvalue())
        self.mdata = out
        self.invisible = True
        return

