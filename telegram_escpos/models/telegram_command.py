from ..escpos import encode_str


from escpos.printer import Network


from openerp import api
from openerp import models


class TelegramCommand(models.Model):

    _inherit = "telegram.command"

    @api.multi
    def _get_globals_dict(self):
        res = super(TelegramCommand, self)._get_globals_dict()
        res['EscposNetworkPrinter'] = Network
        res['escpos_encode'] = encode_str
        return res
