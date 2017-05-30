# Telegram Bot for odoo

Set of modules to run a [telegram](https://telegram.org/) [bot](https://telegram.org/blog/bot-revolution) on [odoo](https://www.odoo.com/) server.

Description and Documentation: https://apps.odoo.com/apps/modules/10.0/telegram

## Getting started

Create your bot via [BotFather](https://telegram.me/botfather). It gives you access token that you will use later.

Install odoo with telegram modules and dependencies via set of [docker](https://docs.docker.com/engine/installation/) containers:

    docker network create odoo-telegram

    docker run \
    -d \
    -e POSTGRES_USER=odoo \
    -e POSTGRES_PASSWORD=odoo \
    --network=odoo-telegram \
    --name db-telegram  \
    postgres:9.5

    docker run \
    -d \
    --name odoo \
    --network=odoo-telegram \
    -e ODOO_MASTER_PASS=admin \
    -e DB_PORT_5432_TCP_ADDR=db-telegram \
    -t itprojectsllc/install-odoo:10.0-telegram -- -d telegram

    # before executing this stop nginx or apache if you have one
    docker run  \
    -d \
    -p 80:80 \
    --name telegram-nginx \
    --network=odoo-telegram \
    -t itprojectsllc/docker-odoo-nginx


Open http://localhost/ (you may need to wait few minutes on first open) and login with login *admin* and password *admin*.

Then install some telegram modules (use search box and don't forget to remove *Apps* filter).

Open *Technical / Parameters / System Parameters* menu. Put access token to *telegram.token* parameter. 

Now you can send /help command to your bot!

For futher usage see [documentation of main module](https://apps.odoo.com/apps/modules/10.0/telegram/) (skip installation part) or documentation of other installed telegram modules. 

## Donation

Feel free to support our development by purchasing [one](https://apps.odoo.com/apps/modules/10.0/telegram) or [two](https://apps.odoo.com/apps/modules/10.0/telegram_chart/) modules.
