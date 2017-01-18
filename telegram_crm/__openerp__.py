# -*- coding: utf-8 -*-
{
    "name": """Telegram CRM""",
    "summary": """Bot commands for CRM application""",
    "category": "Telegram",
    "images": [],
    "version": "1.0.0",

    "author": "IT-Projects LLC, Ivan Yelizariev",
    "support": "apps@it-projects.info",
    "website": "https://it-projects.info",
    "license": "LGPL-3",
    "price": 40.00,
    "currency": "EUR",

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
