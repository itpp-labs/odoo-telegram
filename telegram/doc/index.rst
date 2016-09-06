=============
 User manual
=============

Installation
============

Base dependencies
-----------------

Install foloowing python libs::

    pip2 install -U requests
    pip2 install 'requests[security]'
    pip2 install pyTelegramBotAPI

Charts
------

Install module `Charts for Telegram Bot <https://apps.odoo.com/apps/modules/9.0/telegram_chart/>`__ to be able receive charts. In that case `install Pygal lib <http://www.pygal.org/en/stable/installing.html>`__ too::

    sudo apt-get install libffi-dev
    sudo pip install pygal
    sudo pip install cairosvg tinycss cssselect

Modules
-------

`Install <https://odoo-development.readthedocs.io/en/latest/odoo/usage/install-module.html>`__ this module in a usual way.

You can install other `Telegram modules <https://apps.odoo.com/apps/modules/category/Telegram/browse?author=IT-Projects%20LLC>`__ to have prepared bot commands. Otherwise you will need to create them yourself (see below).

Odoo parameters
---------------

* `Activate longpolling <https://odoo-development.readthedocs.io/en/latest/admin/longpolling.html>`__ 
* Add ``telegram`` to ``--load`` parameters, e.g.::

    ./openerp-server --workers=2 --load telegram,web --config=/path/to/openerp-server.conf

Configuration
=============

* First of all you need to create your own telegram bot if you don't have it yet. Follow `official manual <https://core.telegram.org/bots#3-how-do-i-create-a-bot>`__
* `Enable technical features <https://odoo-development.readthedocs.io/en/latest/odoo/usage/technical-features.html>`__
* Open ``Technical / Parameters / System Parameters`` menu.

  * Enter value for ``telegram.token``. This is yours telegram bot token that *bot father* provided to you.
  * Optional. Enter value for ``telegram.num_odoo_threads``. Number of odoo threads that may to run some tasks (calculations, reports preparation and so on) received form bot. Default value is 2.
  * Opntional. Enter value for ``telegram.num_telegram_threads``. If you have lots of users per database you may be prefer to have bunch of telegram threads that handles requests from telegram clients to increase response speed. Default value is 2.


Usage
=====

* Open telegram.
* Find your bot in contacts and send ``/login`` message (command)
* As answer you will get link you need to follow.
* Your default internet browser will be opened and you will find your self on Odoo login page.
* Enter your Odoo login and password and press ``[Log in]``.
* Now you are logged in.
* If you already logged in Odoo on your device Odoo main page just will be opened and there is no necessity to enter your login and password.

Now you can use commands to Odoo. For example ``/users`` will give you list of users. Send ``/help`` to get list of all available commands.


Creating new commands
=====================

* Open ``Settings / Telegram / Telegram Commands`` menu
* Click ``[Create]``
* Follow hints to fill the form out
* Click ``[Save]``

If command type is not ``Normal``, then you have to make further configuration:

* `Enable technical features <https://odoo-development.readthedocs.io/en/latest/odoo/usage/technical-features.html>`__

For periodic reports:

* Open ``Settings / Technical / Automation / Scheduled Actions``
* Click ``[Create]``
* At ``Technical Data`` tab specify:

  * **Object**: ``telegram.command``
  * **Method**: ``action_handle_subscriptions``
  * **Arguments**: ``(123,)``, where 123 is a ID of you command (can be found in url, when you open command form)

* Click ``[Save]``

For notifications:

* Open ``Settings / Technical / Automation / Automated Actions``
* Click ``[Create]``

* At ``Conditions`` tab specify:

  * **When to Run**, e.g. ``On Creation & Update``
  * **Filter** if needed

* At ``Conditions`` tab specify:

  * **Server actions to run** - select ``Telegram: handle subscriptions (finds commands via "Related models" field)``

* Click ``[Save]``

For speeding up responses:

* Open ``Settings / Technical / Automation / Automated Actions``
* Click ``[Create]``

* At ``Conditions`` tab specify:

  * **When to Run**, e.g. ``On Creation & Update``
  * **Filter** if needed

* At ``Conditions`` tab specify:

  * **Server actions to run** - select ``Telegram: Update cache (finds commands via "Related models" field)``

* Click ``[Save]``
