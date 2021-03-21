# -*- coding: utf-8 -*-
{
    "name": """Telegram CRM""",
    "summary": """Bot commands for CRM application""",
    "category": "Telegram",
    "images": [],
    "version": "1.0.0",

    "author": "IT-Projects LLC, Ivan Yelizariev",
    "website": "https://twitter.com/OdooFree",
    "license": "GPL-3",

    "depends": [
        "telegram_chart",
        "crm",
    ],
    "external_dependencies": {"python": [], "bin": []},

    "data": [
        'data/telegram_command.xml',
    ],
    "qweb": [
    ],
    "demo": [
    ],

    "post_load": None,
    "pre_init_hook": None,
    "post_init_hook": None,
    "installable": True,
    "auto_install": False,
}
