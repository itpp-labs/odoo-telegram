# -*- coding: utf-8 -*-
{
    "name": """Telegram Expense Manager""",
    "summary": """Expense Manager Bot""",
    "category": "Telegram",
    "images": [],
    "version": "1.0.0",
    "application": False,

    "author": "IT-Projects LLC, Ivan Yelizariev",
    "support": "apps@it-projects.info",
    "website": "https://twitter.com/OdooFree",
    "license": "LGPL-3",

    "depends": [
        "telegram",
        "telegram_portal",
        "telegram_chart",
        "account",
        "analytic",
        "l10n_generic_coa",
    ],
    "external_dependencies": {"python": [], "bin": []},
    "data": [
        "data/telegram_command.xml",
        "data/account.xml",
        "data/analytic.xml",
        "data/cron.xml",
        "views/schedule.xml",
        "views/account_account.xml",
        "security/ir.model.access.csv",
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
