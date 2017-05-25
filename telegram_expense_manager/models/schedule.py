# -*- coding: utf-8 -*-
import logging

from datetime import timedelta

from odoo import models, fields, api

_logger = logging.getLogger(__name__)

class Schedule(models.Model):

    _name = "account.schedule"

    def _type_tags(self):
        return [
            self.env.ref(self.env['telegram.command'].TAG_RECEIVABLE).id,
            self.env.ref(self.env['telegram.command'].TAG_LIQUIDITY).id,
            self.env.ref(self.env['telegram.command'].TAG_PAYABLE).id,
        ]

    name = fields.Char('Name')
    active = fields.Boolean('Active', default=True)

    user_id = fields.Many2one(
        'res.users',
        string='User',
        required=True,
        default=lambda self: self.env.user.id,
    )
    partner_id = fields.Many2one(
        'res.partner',
        related='user_id.partner_id'
    )

    from_tag_id = fields.Many2one(
        'account.analytic.tag',
        string='Type',
        #required=True,
        domain=lambda self: [('id', 'in',
                              [
                                  self.env.ref(self.env['telegram.command'].TAG_RECEIVABLE).id,
                                  self.env.ref(self.env['telegram.command'].TAG_LIQUIDITY).id,
                              ]
        )]
    )

    from_analytic_id = fields.Many2one(
        'account.analytic.account',
        string='Analytic',
        domain="""[
            ('partner_id', '=', partner_id),
            ('tag_ids', '=', from_tag_id),
        ]"""
    )

    to_tag_id = fields.Many2one(
        'account.analytic.tag',
        string='Type',
        #required=True,
        domain=lambda self: [('id', 'in',
                              [
                                  self.env.ref(self.env['telegram.command'].TAG_LIQUIDITY).id,
                                  self.env.ref(self.env['telegram.command'].TAG_PAYABLE).id,
                              ]
        )]
    )

    to_analytic_id = fields.Many2one(
        'account.analytic.account',
        string='Analytic',
        domain="""[
            ('partner_id', '=', partner_id),
            ('tag_ids', '=', to_tag_id),
        ]"""
    )

    periodicity_type = fields.Selection([
        ('day', 'Daily'),
        ('week', 'Weekly'),
        ('month', 'Monthly'),
    ], string='Periodicity Type')

    periodicity_amount = fields.Integer('Periodicity Amount')
    date = fields.Datetime('Start point',
                           default=fields.Datetime.now,
                           help="""Start point to compute next date.
                           Equal to creation date, manually set value or last action date""")
    next_date = fields.Datetime('Next Action',
                                help="Date of next activation",
                                compute="_compute_next_date",
                                store=True,
    )

    currency_id = fields.Many2one(
        'res.currency',
        string='Account Currency',
        default=lambda self: self.env.user.company_id.currency_id,
    )
    amount = fields.Monetary('Amount', help='Amount of money to be transfered')
    notify = fields.Selection([
        ('no', "Don't notify"),
        ('instantly', "Notify instantly"),
        # TODO: we can add daily summary notification
    ], string='Notify on transfer', help='Notify user in telegram about created transfer')


    @api.depends('date', 'periodicity_type', 'periodicity_amount')
    def _compute_next_date(self):
        for r in self:
            if not r.periodicity_type or not r.periodicity_amount:
                r.next_date = None
            start = r.date
            if not start:
                start = fields.Datetime.now()
            start = fields.Datetime.from_string(start)
            days = r.periodicity_amount
            if r.periodicity_type == 'week':
                days *= 7
            elif r.periodicity_type == 'monthly':
                # FIXME: this shifts day of month. It must be, for example, ever 21st day of month, instead of +30 days since last date
                days *= 30
            r.next_date = fields.Datetime.to_string(start + timedelta(days=days))

    @api.model
    def action_scheduled_transfers(self):
        self.search([('next_date', '<=', fields.Datetime.now())]).action_transfer_now()

    @api.multi
    def action_transfer_now(self):
        for schedule in self:
            # create record
            # see em_add_record_from_schedule in api.py file
            record = self.env.user.partner_id.em_add_record_from_schedule(schedule=schedule)
            _logger.debug("Scheduled by %s transfer is created: %s", schedule, record)
            # notify
            if schedule.notify == 'instantly':
                command = self.env.ref('telegram_expense_manager.command_schedule')
                tsession = self.env['telegram.session'].sudo().search([('user_id', '=', schedule.user_id.id)])
                command.send_notifications(tsession=tsession, record=record)

            # update date
            schedule.date = fields.Datetime.now()
