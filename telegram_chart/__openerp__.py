# -*- coding: utf-8 -*-
{
    "name": """Charts for Telegram Bot""",
    "summary": """Technical module for chart support""",
    "category": "Hidden",
    "images": [],
    "version": "1.0.0",

    "author": "IT-Projects LLC, Ivan Yelizariev",
    "website": "https://it-projects.info",
    "license": "GPL-3",
    "price": 200.00,
    "currency": "EUR",

    "depends": [
        "telegram",
    ],
    "external_dependencies": {"python": [
        'pygal',
        'cairosvg',
        'tinycss',
        'cssselect',
        'lxml',
    ], "bin": []},

    "data": [
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
