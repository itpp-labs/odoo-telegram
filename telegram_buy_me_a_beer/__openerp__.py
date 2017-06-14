# -*- coding: utf-8 -*-
{
    "name": """Buy me a beer bot""",
    "summary": """Please, :-)""",
    "category": "Telegram",
    "live_test_URL": "t.me/buy_me_a_beer_bot",
    "images": [],
    "version": "1.0.0",
    "application": False,

    "author": "IT-Projects LLC, Ivan Yelizariev",
    "support": "apps@it-projects.info",
    "website": "https://twitter.com/yelizariev",
    "license": "LGPL-3",
    # "price": 9.00,
    # "currency": "EUR",

    "depends": [
        "telegram_portal",
    ],
    "external_dependencies": {"python": [], "bin": []},
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
