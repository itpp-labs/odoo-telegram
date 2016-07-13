==============
 Telegram bot
==============


The module apply monkey patch for PreforkServer in order to run new process Telegram Worker, which run following threads

* Telegram worker - 1 process
  * dispatch -- 1 thread -- instance of TelegramDispatch -- evented tread to listen and notify about events from other odoo processes
    * To send events the function registry['telegram.bus'].sendone() is used
  * OdooTelegramThread - 1 thread - listen for events from odoo_dispatch and delegate work to odoo_thread_pool
  * odoo_thread_pool - pool of threads to handle odoo events.  Executes registry['telegram.command'].telegram_listener() It has 1 + N1+N2+... threads, where Ni is a value of telegram.odoo_threads ir.config_parameter of some database.

  * BotPollingThread - 1 per each database with token - calls bot.polling() function
    * telebot's polling_thread - 1 thread to listen for events from Telegram and delegate work to  telebot's worker_pool
    * telebot's worker_pool -  pool of thread to handle telegram events. Executes registry['telegram.command'].telegram_listener(). It has threads number equal to telegram.telegram_threads ir.config_parameter.

Further information
-------------------

HTML Description: https://apps.odoo.com/apps/modules/9.0/telegram

Usage instructions: `<doc/index.rst>`_

Changelog: `<doc/changelog.rst>`_

Tested on Odoo 9.0 d3dd4161ad0598ebaa659fbd083457c77aa9448d
