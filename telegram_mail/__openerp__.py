# -*- coding: utf-8 -*-
{
    "name": """Telegram mail command""",
    "summary": """Subscribe to incoming odoo mail""",
    "category": "Web",
    "images": [],
    "version": "1.0.0",

    "author": "IT-Projects LLC",
    "website": "https://it-projects.info",
    "license": "GPL-3",
    "price": 40.00,
    "currency": "EUR",

    "depends": [
        "telegram",
    ],
    "external_dependencies": {},
    "data": [
        "data/ir_action_rules.xml",
        "data/command.xml",
    ],
    "qweb": [
    ],
    "demo": [
    ],

    "installable": True,
    "auto_install": False,

}
