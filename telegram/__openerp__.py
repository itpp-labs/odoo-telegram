# -*- encoding: utf-8 -*-
{
    'name': 'Telegram',
    'description' : 'Telegram bot service',
    'category': 'Base',
    'version': '1.0.0',
    'author': 'IT Projects',
    'website': '',
    'depends': ['base', 'web'],
    'auto_install': False,
    'installable': True,
    'post_load' : 'telegram_worker',
}
