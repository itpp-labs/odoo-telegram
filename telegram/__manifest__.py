# -*- coding: utf-8 -*-
{
    "name": """Telegram Bot""",
    "summary": """Your best assistant!""",
    "category": "Telegram",
    "images": [],
    "version": "1.0.0",

    "author": "IT-Projects LLC",
    "support": "apps@it-projects.info",
    "website": "https://it-projects.info",
    "license": "LGPL-3",
    "price": 200.00,
    "currency": "EUR",

    "depends": [
        "base",
        "web",
        "base_automation",
    ],
    "external_dependencies": {"python": [
        'telebot',
        'emoji',
    ], "bin": []},
    "data": [
        "data/config_parameter.xml",
        "data/ir_action_server.xml",
        "data/base_action_rules.xml",
        "data/commands.xml",
        "security/ir.model.access.csv",
        "security/telegram_security.xml",
        "views/telegram_views.xml",
        "views/telegram_command_views.xml",
    ],
    "qweb": [
    ],
    "demo": [
    ],

    'post_load': 'telegram_worker',
    "pre_init_hook": None,
    "post_init_hook": None,
    "installable": True,
    "auto_install": False,
    "application": True,
}
