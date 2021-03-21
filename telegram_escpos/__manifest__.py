# -*- coding: utf-8 -*-
{
    "name": """Print text to escpos printer""",
    "summary": """Use it for fun :-)""",
    "category": "Telegram",
    # "live_test_URL": "",
    "images": [],
    "version": "1.0.0",
    "application": False,

    "author": "IT-Projects LLC, Ivan Yelizariev",
    "support": "apps@it-projects.info",
    "website": "https://twitter.com/OdooFree",
    "license": "LGPL-3",

    "depends": [
        "telegram",
    ],
    "external_dependencies": {"python": ['escpos'], "bin": []},
    "data": [
        "data/telegram_command.xml",
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
