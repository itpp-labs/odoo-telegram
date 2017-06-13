# -*- coding: utf-8 -*-
import logging

from openerp import api
from openerp import models

from ..escpos import encode_str

_logger = logging.getLogger(__name__)

try:
    from escpos.printer import Network
except ImportError as err:
    _logger.debug(err)


class TelegramCommand(models.Model):

    _inherit = "telegram.command"

    @api.multi
    def _get_globals_dict(self):
        res = super(TelegramCommand, self)._get_globals_dict()
        res['EscposNetworkPrinter'] = Network
        res['escpos_encode'] = encode_str
        return res
