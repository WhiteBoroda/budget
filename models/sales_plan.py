# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import ValidationError


class SalesPlan(models.Model):
    """План продажів - базовий документ для бюджетування"""
    _name = 'budget.sales.plan'
    _description = 'План продажів'
    _order = 'period_id desc, company_id'
    _rec_name = 'display_name'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    @api.depends('period_id', 'company_id')
    def _compute_display_name(self):
        for record in self:
            record.display_name = f"План продажів {record.company_id.name} - {record.period_id.name}"

    display_name = fields.Char('Назва', compute='_compute_display_name', store=True)

    period_id = fields.Many2one('budget.period', 'Період', required=True)
    company_id = fields.Many2one('res.company', 'Підприємство', required=True, default=lambda self: self.env.company)

    state = fields.Selection([
        ('draft', 'Чернетка'),
        ('analysis', 'Аналіз'),
        ('project', 'Проект'),
        ('coordination', 'Узгодження'),
        ('approved', 'Затверджений'),
        ('revision', 'Перегляд')
    ], 'Статус', default='draft', required=True, tracking=True)

    total_planned_amount = fields.Monetary('Загальна сума плану', compute='_compute_totals', store=True)
    total_planned_qty = fields.Float('Загальна кількість', compute='_compute_totals', store=True)

    responsible_user_id = fields.Many2one('res.users', 'Відповідальний', default=lambda self: self.env.user,
                                          required=True)
    approved_by_id = fields.Many2one('res.users', 'Затверджено')
    approval_date = fields.Datetime('Дата затвердження')

    currency_id = fields.Many2one('res.currency', related='company_id.currency_id', readonly=True)

    # Лінії плану продажів
    line_ids = fields.One2many('budget.sales.plan.line', 'plan_id', 'Позиції плану')

    # Аналітичні поля
    previous_period_sales = fields.Monetary('Продажі попереднього періоду', readonly=True)
    growth_rate = fields.Float('Темп росту, %', compute='_compute_growth_rate', store=True)

    notes = fields.Text('Примітки')

    @api.depends('line_ids.planned_amount', 'line_ids.planned_qty')
    def _compute_totals(self):
        for record in self:
            record.total_planned_amount = sum(record.line_ids.mapped('planned_amount'))
            record.total_planned_qty = sum(record.line_ids.mapped('planned_qty'))

    @api.depends('total_planned_amount', 'previous_period_sales')
    def _compute_growth_rate(self):
        for record in self:
            if record.previous_period_sales:
                record.growth_rate = ((record.total_planned_amount - record.previous_period_sales) /
                                      record.previous_period_sales) * 100
            else:
                record.growth_rate = 0.0

    def action_start_analysis(self):
        """Переведення в стан аналізу"""
        self.state = 'analysis'

    def action_create_project(self):
        """Створення проекту плану"""
        self.state = 'project'

    def action_send_for_coordination(self):
        """Відправка на узгодження"""
        self.state = 'coordination'

    def action_approve(self):
        """Затвердження плану"""
        self.write({
            'state': 'approved',
            'approved_by_id': self.env.user.id,
            'approval_date': fields.Datetime.now()
        })

    def action_revise(self):
        """Перегляд плану"""
        self.state = 'revision'


class SalesPlanLine(models.Model):
    """Позиції плану продажів"""
    _name = 'budget.sales.plan.line'
    _description = 'Позиції плану продажів'

    plan_id = fields.Many2one('budget.sales.plan', 'План продажів', required=True, ondelete='cascade')

    product_id = fields.Many2one('product.product', 'Товар')
    product_category_id = fields.Many2one('product.category', 'Категорія товару')

    sales_channel = fields.Selection([
        ('b2b', 'B2B'),
        ('retail', 'Роздрібна мережа'),
        ('export', 'Експорт'),
        ('other', 'Інше')
    ], 'Канал збуту', required=True)

    region = fields.Selection([
        ('local', 'Місцевий'),
        ('regional', 'Регіональний'),
        ('national', 'Національний'),
        ('export', 'Експорт')
    ], 'Регіон збуту', required=True)

    planned_qty = fields.Float('Планова кількість', required=True)
    planned_price = fields.Monetary('Планова ціна', required=True)
    planned_amount = fields.Monetary('Планова сума', compute='_compute_amount', store=True)

    discount_percent = fields.Float('Знижка, %', default=0.0)
    return_percent = fields.Float('Відсоток повернень, %', default=0.0)

    currency_id = fields.Many2one('res.currency', related='plan_id.company_id.currency_id', readonly=True)

    notes = fields.Text('Примітки')

    @api.depends('planned_qty', 'planned_price', 'discount_percent')
    def _compute_amount(self):
        for line in self:
            amount = line.planned_qty * line.planned_price
            if line.discount_percent:
                amount *= (1 - line.discount_percent / 100)
            line.planned_amount = amount