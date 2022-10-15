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

class TelegramSession(models.Model):
    _inherit = 'telegram.session'

    partner_id = fields.Many2one('res.partner', 'Partner')

    @api.multi
    def get_partner(self):
        self.ensure_one()
        return self.partner_id or 0
