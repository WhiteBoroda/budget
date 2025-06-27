# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import ValidationError


class BudgetPlan(models.Model):
    """Основний документ бюджетного планування"""
    _name = 'budget.plan'
    _description = 'Бюджетний план'
    _order = 'period_id desc, level, cbo_id'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    def _compute_display_name(self):
        for record in self:
            budget_type_name = record.budget_type_id.name if record.budget_type_id else 'Без типу'
            cbo_name = record.cbo_id.name if record.cbo_id else 'Без ЦБО'
            period_name = record.period_id.name if record.period_id else 'Без періоду'
            record.display_name = f"{budget_type_name} - {cbo_name} ({period_name})"

    display_name = fields.Char('Назва', compute='_compute_display_name', store=False)

    period_id = fields.Many2one('budget.period', 'Період', required=True)
    cbo_id = fields.Many2one('budget.responsibility.center', 'ЦБО', required=True)
    budget_type_id = fields.Many2one('budget.type', 'Тип бюджету', required=True)

    level = fields.Selection([
        ('level3', '3 рівень (ЦБО)'),
        ('level2', '2 рівень (ПП)'),
        ('level1', '1 рівень (Консолідований)')
    ], 'Рівень бюджету', required=True, default='level3')

    state = fields.Selection([
        ('draft', 'Чернетка'),
        ('planning', 'Планування'),
        ('coordination', 'Узгодження'),
        ('approved', 'Затверджений'),
        ('revision', 'Доопрацювання')
    ], 'Статус', default='draft', required=True, tracking=True)

    planned_amount = fields.Monetary('Планова сума', compute='_compute_totals', store=True)
    actual_amount = fields.Monetary('Фактична сума', readonly=True)
    variance_amount = fields.Monetary('Відхилення', compute='_compute_variance', store=True)
    variance_percent = fields.Float('Відхилення, %', compute='_compute_variance', store=True)

    responsible_user_id = fields.Many2one('res.users', 'Відповідальний планувальник', required=True,
                                          default=lambda self: self.env.user)
    coordinator_user_id = fields.Many2one('res.users', 'Координатор УК')
    approved_by_id = fields.Many2one('res.users', 'Затверджено')

    company_id = fields.Many2one('res.company', 'Підприємство', required=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id', readonly=True)

    # Зв'язок з планом продажів
    sales_plan_id = fields.Many2one('budget.sales.plan', 'План продажів')

    # Лінії бюджету
    line_ids = fields.One2many('budget.plan.line', 'plan_id', 'Позиції бюджету')

    # Консолідація
    parent_budget_id = fields.Many2one('budget.plan', 'Батьківський бюджет')
    child_budget_ids = fields.One2many('budget.plan', 'parent_budget_id', 'Дочірні бюджети')

    # Метадані
    submission_deadline = fields.Date('Крайній термін подання', required=True)
    approval_date = fields.Datetime('Дата затвердження')

    notes = fields.Text('Примітки')

    @api.depends('line_ids.planned_amount')
    def _compute_totals(self):
        for record in self:
            record.planned_amount = sum(record.line_ids.mapped('planned_amount'))

    @api.depends('planned_amount', 'actual_amount')
    def _compute_variance(self):
        for record in self:
            record.variance_amount = record.actual_amount - record.planned_amount
            if record.planned_amount:
                record.variance_percent = (record.variance_amount / record.planned_amount) * 100
            else:
                record.variance_percent = 0.0

    def action_start_planning(self):
        """Початок планування"""
        self.state = 'planning'

    def action_send_coordination(self):
        """Відправка на узгодження"""
        self.state = 'coordination'

    def action_approve(self):
        """Затвердження бюджету"""
        self.write({
            'state': 'approved',
            'approved_by_id': self.env.user.id,
            'approval_date': fields.Datetime.now()
        })

    def action_request_revision(self):
        """Відправка на доопрацювання"""
        self.state = 'revision'


class BudgetPlanLine(models.Model):
    """Позиції бюджетного плану"""
    _name = 'budget.plan.line'
    _description = 'Позиції бюджетного плану'

    plan_id = fields.Many2one('budget.plan', 'Бюджетний план', required=True, ondelete='cascade')

    account_id = fields.Many2one('account.account', 'Рахунок')
    analytic_account_id = fields.Many2one('account.analytic.account', 'Аналітичний рахунок')

    description = fields.Char('Опис', required=True)
    planned_amount = fields.Monetary('Планова сума', required=True)

    calculation_basis = fields.Text('Основа розрахунку')
    calculation_method = fields.Selection([
        ('manual', 'Ручний ввід'),
        ('norm_based', 'За нормативами'),
        ('percentage', 'Відсоток від доходів'),
        ('previous_period', 'На основі попереднього періоду')
    ], 'Метод розрахунку', default='manual')

    quantity = fields.Float('Кількість')
    unit_price = fields.Monetary('Ціна за одиницю')

    currency_id = fields.Many2one('res.currency', related='plan_id.company_id.currency_id', readonly=True)

    # Аналітичні виміри
    department_id = fields.Many2one('hr.department', 'Підрозділ')
    project_id = fields.Many2one('project.project', 'Проект')

    notes = fields.Text('Примітки')