# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (c) 2018 Real Systems. All Rights Reserved.
#    Author: Carlos Contreras <carlosecv@realsystems.com.mx>
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from num2words import num2words
from odoo import api, fields, models, tools, _
from datetime import datetime, timedelta

from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT, float_compare
from odoo.exceptions import UserError

from itertools import groupby

import urllib as my_urllib

from odoo.addons.base_geoengine import fields as geo_fields
from odoo.addons.base_geoengine import geo_model
from odoo.exceptions import ValidationError

import simplejson as json

import logging

_logger = logging.getLogger(__name__)

try:
    from pyproj import Proj, transform
    import geojson
except ImportError:
    _logger.debug('Cannot `import pyproj or geojson`.')


try:
    import googlemaps
except ImportError:
    _logger.debug('Cannot `import googlemaps`.')

from datetime import datetime


class DeliveryReceipt(models.Model):
    _name = 'rs.delivery.receipt'
    _description = 'Delivery Sale Receipt'

    name = fields.Char('Folio Number', readonly=True, index=True,
                       default='New')
    order_id = fields.Many2one('sale.order', 'Order', required=False, ondelete='cascade')

    partner_id = fields.Many2one('res.partner', 'Customer',
                               required=False )

    delivered_record = fields.Float('Delivered Amount',
                            help="Number indicated on delivery "
                            "count from the Pipe. ")

    date = fields.Datetime(
        'Date registered', required=True,
        default=(fields.Datetime.now))

    date_delivered = fields.Datetime(
        'Date delivered', required=False)

    latitude = fields.Float(
        required=False, digits=(20, 10),
        help='GPS Latitude')

    longitude = fields.Float(
        required=False, digits=(20, 10),
        help='GPS Longitude')

    point = geo_fields.GeoPoint(
        string='Coordinate',
        compute='_compute_point',
        inverse='_set_lat_long',
    )

    state = fields.Selection([
        ('draft', 'Pendiente'),
        ('waiting', 'Customer Waiting'),
        ('done', 'Surtido'),
        ('cancel', 'Cancelled'),
        ], string='Status', readonly=True, copy=False, index=True, track_visibility='onchange', default='draft')


    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            if 'company_id' in vals:
                vals['name'] = self.env['ir.sequence'].with_context(force_company=vals['company_id']).next_by_code('rs.delivery.receipt') or _('New')
            else:
                vals['name'] = self.env['ir.sequence'].next_by_code('rs.delivery.receipt') or _('New')
        result = super(DeliveryReceipt, self).create(vals)
        return result

    @api.depends('partner_id')
    def _telegram_info(self):
        for rec in self:
            self.rs_telegram_address=rec.partner_id.rs_telegram_address
            self.latitude=rec.partner_id.rs_telegram_latitude
            self.longitude=rec.partner_id.rs_telegram_longitude

    @api.depends('latitude', 'longitude')
    def _compute_point(self):
        for rec in self:
            rec.point = geo_fields.GeoPoint.from_latlon(
                self.env.cr, rec.latitude, rec.longitude).wkb_hex

    def set_lang_long(self):
        try:
            point_x, point_y = geojson.loads(self.point)['coordinates']
            inproj = Proj(init='epsg:3857')
            outproj = Proj(init='epsg:4326')
            longitude, latitude = transform(inproj, outproj, point_x, point_y)
            self.latitude = latitude
            self.longitude = longitude
        except Exception as e:
            pass

    @api.onchange('point')
    def onchange_geo_point(self):
        if self.point:
            self.set_lang_long()

    @api.depends('point')
    def _set_lat_long(self):
        for rec in self:
            if rec.point:
                rec.set_lang_long()
