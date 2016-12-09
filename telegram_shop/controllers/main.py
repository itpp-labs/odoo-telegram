from openerp import http
from openerp.http import request
from openerp.addons.web.controllers.main import login_redirect


class telegram_website_sale(http.Controller):

    @http.route(['/shop/telegram_cart/<int:sale_order_id>'], type='http', auth="public", website=True)
    def telegram_cart(self, sale_order_id):
        sale_order = request.env['sale.order'].sudo().browse(sale_order_id)
        if request.env.user.partner_id != sale_order.partner_id:
            return login_redirect()
        request.session['sale_order_id'] = sale_order.id
        return request.redirect('/shop/cart')
