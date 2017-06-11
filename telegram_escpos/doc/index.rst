==============================
 Print text to escpos printer
==============================

To use this module you need:

* odoo
* telegram account
* network escpos printer
* idea what to print

Installation
============

* Install `Telegram Bot <https://www.odoo.com/apps/modules/10.0/telegram/>`__ module
* `Enable technical features <https://odoo-development.readthedocs.io/en/latest/odoo/usage/technical-features.html>`__
* Open ``Technical / Parameters / System Parameters`` menu.

  * Enter value for ``telegram_escpos.host`` and ``telegram_escpos.port``

Usage
=====

* Send ``/print Hello World!`` to your bot
