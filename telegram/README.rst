==============
 Telegram bot
==============


The module apply monkey patch for ``PreforkServer`` in order to run new process ``WorkerTelegram``, which run threads as following:

* ``WorkerTelegram`` (1 process)

  * ``odoo_dispatch`` (1 thread)

    * Instance of ``TelegramDispatch`` (evented tread to listen and notify about events from other odoo processes).
    * To send events the function ``registry['telegram.bus'].sendone()`` is used

  * ``OdooTelegramThread`` (1 thread per each database)

    * Listen for events from ``odoo_dispatch`` and delegate work to ``odoo_thread_pool``
    * ``odoo_thread_pool`` (1 pool)

      * Pool of threads to handle odoo events.
      * Handles updates of telegram parameters 
      * Executes ``registry['telegram.command'].odoo_listener()``
      * Has threads number equal to ``telegram.num_odoo_threads`` parameter.

  * ``BotPollingThread``  (1 thread per each database with token)

    * Calls ``bot.polling()`` function
    * telebot's ``polling_thread`` (1 thread)

      * Listen for events from Telegram and delegate work to telebot's ``worker_pool``

    * telebot's ``worker_pool`` (1 pool)

      * Pool of thread to handle telegram events.
      * Executes ``registry['telegram.command'].telegram_listener()``.
      * Has threads number equal to ``telegram.num_telegram_threads`` parameter.

Docker installation
-------------------
You can use a `docker <https://github.com/it-projects-llc/install-odoo/blob/master/dockers/telegram/Dockerfile>`__ to easily run Telegram Bot::

    docker run \
    -p 8069:8069 \
    -p 8072:8072 \
    --name telegram \
    --link db-telegram:db \
    -t itprojectsllc/install-odoo:10.0-telegram


Further information
-------------------

HTML Description: https://apps.odoo.com/apps/modules/9.0/telegram

Usage instructions: `<doc/index.rst>`__

Changelog: `<doc/changelog.rst>`__

Tested on Odoo 8.0 7b93e1dc7b4a370c312b64afda7a6045bdb81f38
