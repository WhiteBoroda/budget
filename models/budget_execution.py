# -*- coding: utf-8 -*-

from odoo import models, fields, api


class BudgetExecution(models.Model):
    """Виконання бюджету"""
    _name = 'budget.execution'
    _description = 'Виконання бюджету'
    _order = 'date desc'

    budget_plan_id = fields.Many2one('budget.plan', 'Бюджетний план', required=True)
    date = fields.Date('Дата', required=True, default=fields.Date.today)

    actual_amount = fields.Monetary('Фактична сума', required=True)
    variance_amount = fields.Monetary('Відхилення', compute='_compute_variance', store=True)
    variance_percent = fields.Float('Відхилення, %', compute='_compute_variance', store=True)

    move_id = fields.Many2one('account.move', 'Облікова проводка')
    move_line_id = fields.Many2one('account.move.line', 'Рядок проводки')

    description = fields.Char('Опис')
    responsible_user_id = fields.Many2one('res.users', 'Відповідальний', default=lambda self: self.env.user)

    currency_id = fields.Many2one('res.currency', related='budget_plan_id.company_id.currency_id', readonly=True)

    @api.depends('actual_amount', 'budget_plan_id.planned_amount')
    def _compute_variance(self):
        for record in self:
            planned = record.budget_plan_id.planned_amount
            record.variance_amount = record.actual_amount - planned
            if planned:
                record.variance_percent = (record.variance_amount / planned) * 100
            else:
                record.variance_percent = 0.0