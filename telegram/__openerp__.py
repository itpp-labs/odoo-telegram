# -*- coding: utf-8 -*-
{
    "name": """Telegram bot""",
    "summary": """Telegram bot service""",
    "category": "Web",
    "images": [],
    "version": "1.0.0",

    "author": "IT-Projects LLC",
    "website": "https://it-projects.info",
    "license": "GPL-3",
    #"price": 9.00,
    #"currency": "EUR",

    "depends": [
        "base",
        "web",
        "base_action_rule",
    ],
    "external_dependencies": {"python": ['telebot'], "bin": []},
    "data": [
        "data/config_parameter.xml",
        "data/ir_action_server.xml",
        "data/it_action_rules.xml",
        "data/commands.xml",
        "security/ir.model.access.csv",
    ],
    "qweb": [
    ],
    "demo": [
    ],

    'post_load' : 'telegram_worker',
    "pre_init_hook": None,
    "post_init_hook": None,
    "installable": True,
    "auto_install": False,

}
