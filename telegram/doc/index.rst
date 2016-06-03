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