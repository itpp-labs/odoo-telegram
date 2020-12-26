# -*- coding: utf-8 -*-
{
    "name": """Telegram Portal""",
    "summary": """Auto sign-up new users""",
    "category": "Telegram",
    "images": [],
    "version": "1.0.0",
    "application": False,

    "author": "IT-Projects LLC, Ivan Yelizariev",
    "support": "apps@it-projects.info",
    "website": "https://twitter.com/yelizariev",
    "license": "LGPL-3",

    "depends": [
        "telegram",
    ],
    "external_dependencies": {"python": [], "bin": []},
    "data": [
        "data/auth_signup_data.xml",
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
