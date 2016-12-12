# -*- coding: utf-8 -*-
from odoo import models, api


class TelegramCommand(models.Model):
    _inherit = 'telegram.command'

    @api.model
    def get_pricelist(self, context):
        sale_order = context.get('sale_order')
        if sale_order:
            sale_order = self.env['sale.order'].sudo().browse(sale_order)
            pricelist = sale_order.pricelist_id
        else:
            partner = self.env.user.partner_id
            pricelist = partner.property_product_pricelist
        return pricelist

    @api.model
    def sale_get_order(self, context):
        sale_order = context.get('sale_order')
        if sale_order:
            sale_order = self.env['sale.order'].sudo().browse(sale_order)

        if sale_order:
            return sale_order

        user = self.env.user
        partner = user.partner_id
        values = {
            'user_id': user.id,
            'partner_id': partner.id,
            'pricelist_id': partner.property_product_pricelist.id,
            'section_id': self.env.ref('sales_team.salesteam_website_sales').id,
        }
        sale_order = self.env['sale.order'].sudo().create(values)
        context['sale_order'] = sale_order.id
        return sale_order
