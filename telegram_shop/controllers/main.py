# -*- coding: utf-8 -*-

import werkzeug
from openerp import http
from openerp.http import request


class TelegramWebsiteSale(http.Controller):

    @http.route(['/shop/telegram_cart/<int:sale_order_id>'], type='http', auth="public", website=True)
    def telegram_cart(self, sale_order_id):
        sale_order = request.env['sale.order'].sudo().browse(sale_order_id)
        if request.env.user.partner_id != sale_order.partner_id:
            query = werkzeug.urls.url_encode({
                'redirect': request.httprequest.url,
            })
            return request.redirect('/web/login?%s' % query)
        request.session['sale_order_id'] = sale_order.id
        return request.redirect('/shop/cart')
