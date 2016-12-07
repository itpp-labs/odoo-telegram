# -*- coding: utf-8 -*-
from openerp import models, api


class TelegramCommand(models.Model):
    _inherit = 'telegram.command'

    @api.model
    def get_pricelist(self, user, context):
        sale_order = context.get('sale_order')
        if sale_order:
            sale_order = self.env['sale.order'].browse(sale_order)
            pricelist = sale_order.pricelist_id
        else:
            partner = user.partner_id
            pricelist = partner.property_product_pricelist
        return pricelist
