# -*- coding: utf-8 -*-
{
    "name": """Telegram Project Issues""",
    "summary": """Bot commands for Project Issue application""",
    "category": "Telegram",
    "images": [],
    "version": "1.0.0",
    "application": False,

    "author": "IT-Projects LLC, Ivan Yelizariev",
    "website": "https://twitter.com/OdooFree",
    "license": "GPL-3",

    "depends": [
        "telegram",
        "project_issue",
    ],
    "external_dependencies": {"python": [], "bin": []},
    "data": [
        "data/telegram_command.xml",
        "data/ir_cron.xml",
    ],
    "qweb": [
    ],
    "demo": [
    ],

    "post_load": None,
    "pre_init_hook": None,
    "post_init_hook": None,

    "auto_install": False,
    "installable": True,
}
