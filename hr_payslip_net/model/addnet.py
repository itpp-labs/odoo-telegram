# -*- coding: utf-8 -*-
from openerp import api, _
from openerp import fields, models

class hr_payslip(models.Model):
    _inherit = 'hr.payslip'
    _description = "This model adds NET field to hr.payslip"
    net = fields.Float('Net amount', compute='_setNetValue', readonly=True, store=True)

    @api.depends('details_by_salary_rule_category.code')
    def _setNetValue(self):
        for rec in self:
            net_lines = [r for r in rec.details_by_salary_rule_category if r.code == 'NET']
            if net_lines.__len__() == 0:
                continue
            rec.net = float(net_lines[0].amount)