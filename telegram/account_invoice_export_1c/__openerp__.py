{
    'name': 'account invoice export 1c',
    'summary' : 'Export invoices in 1C format',
    'version': '1.0.0',
    'category': 'Accounting & Finance',
    'author': 'IT-Projects LLC',
    'license': 'LGPL-3',
    'website': 'https://twitter.com/yelizariev',
    'description': """Для выгрузки счетов (invoice) для банка, чтобы банк использовал их как платежные поручения.

                   Выгружаются только out_invoice (Платежное поручение) и out_refund (Возврат покупателю)
                   т.о. /мы/ всегда выступаем платильщиком.

                   Зависит от локализации l10n_ru OdooRussia исользуются поля ИНН КПП и много чего другого""",
    'depends': ['base', 'account', 'l10n_ru'],
    'data': ['wizard/export_wizard.xml'],
    'installable': True,
}
