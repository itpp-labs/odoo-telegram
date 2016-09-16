# -*- coding: utf-8 -*-

import openerp
import openerp.tools.config as config
from openerp import SUPERUSER_ID
import logging

_logger = logging.getLogger(__name__)


def get_registry(db_name):
    openerp.modules.registry.RegistryManager.check_registry_signaling(db_name)
    registry = openerp.registry(db_name)
    return registry


def get_parameter(dbname, key):
    db = openerp.sql_db.db_connect(dbname)
    registry = get_registry(dbname)
    with openerp.api.Environment.manage(), db.cursor() as cr:
        return registry['ir.config_parameter'].get_param(cr, SUPERUSER_ID, key)


def running_workers_num(workers):
    res = 0
    for r in workers:
        if r._running:
            res += 1
    return res


def db_list():
    if config['db_name']:
        db_names = config['db_name'].split(',')
    else:
        db_names = openerp.service.db.exp_list(True)
    return db_names


def get_int_parameter(dbname, key, default=1):
    num = get_parameter(dbname, key)
    try:
        return int(num)
    except:
        _logger.info('Wrong value of %s: %s', key, num)
    return default


def token_is_valid(token):
    if token and len(token) > 10:
        _logger.debug('Valid token')
        return True
    _logger.debug('Invalid token')
    return False
