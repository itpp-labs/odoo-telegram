# -*- coding: utf-8 -*-
{
    "name": """Telegram Gas Delivery Module""",
    "summary": """Bot commands for GAS Delivery Application""",
    "category": "Telegram",
    "images": [],
    "version": "1.0.0",
    "application": False,

    "author": "Real Systems, Carlos Contreras",
    "support": "ventas@realsystems.com.mx",
    "website": "https://www.realsystems.com.mx",
    "license": "LGPL-3",
    "price": 40.00,
    "currency": "EUR",

    "depends": [
        "telegram",
        "base",
        "sale",
    ],
    "external_dependencies": {"python": ['pyproj','geojson','googlemaps'], "bin": []},
    "data": [
        "data/telegram_command_delivery.xml",
        "views/res_partner_view.xml",
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
