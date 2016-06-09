=============
 User manual
=============


Preparation
===========

1. Install *requests* and *requests[security]* python libs::

    pip2 install -U requests
    pip2 install 'requests[security]'

2. Configure settings:

* Open base.
* Go to ``Technical \ Parameters \ System Parameters``.
* Enter value for ``telegram.token``. This is yours telegram bot token that *bot father* provided to you.
* Enter value for ``telegram.odoo_threads``. Number of odoo threads that may to run some tasks (calculations, reports preparation and so on) received form bot. Default value is 2.
* Enter value for ``telegram.telegram_threads``. If you have lots of users per database you may be prefer to have bunch of telegram threads that handles requests from telegram clients to increase response speed. Default value is 2.

3. Turn off db filter in odoo configuration file.

4. Run odoo with these console keys:  **--workers=2 --load telegram,web**.

Using
-----

First of all you need to login in Odoo with telegram:

* Open telegram.
* Find your bot in contacts and send ``/login`` message (command) to him.
* As answer you will get link you need to follow.
* Your default internet browser will be opened and you will find your self on Odoo login page.
* Enter your Odoo login and password and press ``[Log in]``.
* Now you are logged in.
* If you already logged in Odoo on your device Odoo main page just will be opened and there is no necessity to enter your login and password.
* Now you can use commands to Odoo. For example ``/users`` will give you list of users.