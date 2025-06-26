# -*- coding: utf-8 -*-

from odoo import models, fields, api, tools
from datetime import datetime, timedelta


class BudgetAnalysis(models.Model):
    """Аналіз виконання бюджету"""
    _name = 'budget.analysis'
    _description = 'Аналіз виконання бюджету'
    _auto = False
    _rec_name = 'budget_name'

    budget_name = fields.Char('Назва бюджету', readonly=True)
    period_id = fields.Many2one('budget.period', 'Період', readonly=True)
    company_id = fields.Many2one('res.company', 'Підприємство', readonly=True)
    cbo_id = fields.Many2one('budget.responsibility.center', 'ЦБО', readonly=True)
    budget_type_id = fields.Many2one('budget.type', 'Тип бюджету', readonly=True)

    planned_amount = fields.Monetary('Планова сума', readonly=True)
    actual_amount = fields.Monetary('Фактична сума', readonly=True)
    variance_amount = fields.Monetary('Відхилення', readonly=True)
    variance_percent = fields.Float('Відхилення, %', readonly=True)
    execution_percent = fields.Float('Виконання, %', readonly=True)

    currency_id = fields.Many2one('res.currency', readonly=True)

    def init(self):
        """Створення SQL view для аналізу"""
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                SELECT 
                    bp.id,
                    CONCAT(bt.name, ' - ', cbo.name, ' (', per.name, ')') as budget_name,
                    bp.period_id,
                    bp.company_id,
                    bp.cbo_id,
                    bp.budget_type_id,
                    bp.planned_amount,
                    COALESCE(
                        (SELECT SUM(be.actual_amount) 
                         FROM budget_execution be 
                         WHERE be.budget_plan_id = bp.id), 0
                    ) as actual_amount,
                    COALESCE(
                        (SELECT SUM(be.actual_amount) 
                         FROM budget_execution be 
                         WHERE be.budget_plan_id = bp.id), 0
                    ) - bp.planned_amount as variance_amount,
                    CASE 
                        WHEN bp.planned_amount != 0 THEN
                            ((COALESCE(
                                (SELECT SUM(be.actual_amount) 
                                 FROM budget_execution be 
                                 WHERE be.budget_plan_id = bp.id), 0
                            ) - bp.planned_amount) / bp.planned_amount) * 100
                        ELSE 0
                    END as variance_percent,
                    CASE 
                        WHEN bp.planned_amount != 0 THEN
                            (COALESCE(
                                (SELECT SUM(be.actual_amount) 
                                 FROM budget_execution be 
                                 WHERE be.budget_plan_id = bp.id), 0
                            ) / bp.planned_amount) * 100
                        ELSE 0
                    END as execution_percent,
                    rc.currency_id
                FROM budget_plan bp
                LEFT JOIN res_company rc ON bp.company_id = rc.id
                LEFT JOIN budget_type bt ON bp.budget_type_id = bt.id
                LEFT JOIN budget_responsibility_center cbo ON bp.cbo_id = cbo.id
                LEFT JOIN budget_period per ON bp.period_id = per.id
                WHERE bp.state = 'approved'
            )
        """ % self._table)


class BudgetDashboard(models.Model):
    """Панель керування бюджетуванням"""
    _name = 'budget.dashboard'
    _description = 'Панель керування бюджетуванням'

    name = fields.Char('Назва', default='Панель бюджетування')
    period_id = fields.Many2one('budget.period', 'Поточний період')

    # Статистичні поля
    total_budgets = fields.Integer('Загальна кількість бюджетів', compute='_compute_statistics')
    approved_budgets = fields.Integer('Затверджені бюджети', compute='_compute_statistics')
    pending_budgets = fields.Integer('На узгодженні', compute='_compute_statistics')
    overdue_budgets = fields.Integer('Прострочені', compute='_compute_statistics')

    total_planned = fields.Monetary('Загальна планова сума', compute='_compute_amounts')
    total_actual = fields.Monetary('Загальна фактична сума', compute='_compute_amounts')
    total_variance = fields.Monetary('Загальне відхилення', compute='_compute_amounts')

    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)

    @api.depends('period_id')
    def _compute_statistics(self):
        for record in self:
            if record.period_id:
                budgets = self.env['budget.plan'].search([('period_id', '=', record.period_id.id)])
                record.total_budgets = len(budgets)
                record.approved_budgets = len(budgets.filtered(lambda b: b.state == 'approved'))
                record.pending_budgets = len(budgets.filtered(lambda b: b.state == 'coordination'))
                record.overdue_budgets = len(budgets.filtered(
                    lambda b: b.submission_deadline < fields.Date.today() and b.state != 'approved'
                ))
            else:
                record.total_budgets = 0
                record.approved_budgets = 0
                record.pending_budgets = 0
                record.overdue_budgets = 0

    @api.depends('period_id')
    def _compute_amounts(self):
        for record in self:
            if record.period_id:
                approved_budgets = self.env['budget.plan'].search([
                    ('period_id', '=', record.period_id.id),
                    ('state', '=', 'approved')
                ])
                record.total_planned = sum(approved_budgets.mapped('planned_amount'))
                record.total_actual = sum(approved_budgets.mapped('actual_amount'))
                record.total_variance = record.total_actual - record.total_planned
            else:
                record.total_planned = 0
                record.total_actual = 0
                record.total_variance = 0

    def action_view_budgets(self):
        """Перегляд бюджетів поточного періоду"""
        return {
            'type': 'ir.actions.act_window',
            'name': 'Бюджети поточного періоду',
            'res_model': 'budget.plan',
            'view_mode': 'kanban,tree,form',
            'domain': [('period_id', '=', self.period_id.id)] if self.period_id else [],
            'context': {'default_period_id': self.period_id.id if self.period_id else False}
        }

    def action_view_overdue(self):
        """Перегляд прострочених бюджетів"""
        return {
            'type': 'ir.actions.act_window',
            'name': 'Прострочені бюджети',
            'res_model': 'budget.plan',
            'view_mode': 'tree,form',
            'domain': [
                ('submission_deadline', '<', fields.Date.today()),
                ('state', '!=', 'approved'),
                ('period_id', '=', self.period_id.id) if self.period_id else ('id', '>', 0)
            ]
        }


class BudgetNotification(models.Model):
    """Сповіщення по бюджетуванню"""
    _name = 'budget.notification'
    _description = 'Сповіщення по бюджетуванню'
    _order = 'create_date desc'

    name = fields.Char('Повідомлення', required=True)
    notification_type = fields.Selection([
        ('deadline', 'Нагадування про дедлайн'),
        ('approval', 'Запит на затвердження'),
        ('approved', 'Бюджет затверджено'),
        ('rejected', 'Бюджет відхилено'),
        ('overdue', 'Прострочено')
    ], 'Тип сповіщення', required=True)

    budget_plan_id = fields.Many2one('budget.plan', 'Бюджетний план')
    user_id = fields.Many2one('res.users', 'Користувач', required=True)

    is_read = fields.Boolean('Прочитано', default=False)
    priority = fields.Selection([
        ('low', 'Низький'),
        ('normal', 'Звичайний'),
        ('high', 'Високий'),
        ('urgent', 'Терміновий')
    ], 'Пріоритет', default='normal')

    @api.model
    def create_deadline_notifications(self):
        """Створення нагадувань про дедлайни (викликається з cron)"""
        tomorrow = fields.Date.today() + timedelta(days=1)

        # Знаходимо бюджети з дедлайном завтра
        upcoming_budgets = self.env['budget.plan'].search([
            ('submission_deadline', '=', tomorrow),
            ('state', 'in', ['draft', 'planning'])
        ])

        for budget in upcoming_budgets:
            self.create({
                'name': f'Нагадування: дедлайн подання бюджету {budget.display_name} завтра!',
                'notification_type': 'deadline',
                'budget_plan_id': budget.id,
                'user_id': budget.responsible_user_id.id,
                'priority': 'high'
            })

    @api.model
    def create_overdue_notifications(self):
        """Створення сповіщень про прострочені бюджети"""
        today = fields.Date.today()

        overdue_budgets = self.env['budget.plan'].search([
            ('submission_deadline', '<', today),
            ('state', 'in', ['draft', 'planning'])
        ])

        for budget in overdue_budgets:
            # Перевіряємо чи не було вже створено сповіщення сьогодні
            existing = self.search([
                ('budget_plan_id', '=', budget.id),
                ('notification_type', '=', 'overdue'),
                ('create_date', '>=', datetime.combine(today, datetime.min.time()))
            ])

            if not existing:
                self.create({
                    'name': f'Прострочено: бюджет {budget.display_name} не подано вчасно!',
                    'notification_type': 'overdue',
                    'budget_plan_id': budget.id,
                    'user_id': budget.responsible_user_id.id,
                    'priority': 'urgent'
                })

    def action_mark_read(self):
        """Позначити як прочитане"""
        self.write({'is_read': True})

    def action_open_budget(self):
        """Відкрити пов'язаний бюджет"""
        if self.budget_plan_id:
            return {
                'type': 'ir.actions.act_window',
                'name': 'Бюджетний план',
                'res_model': 'budget.plan',
                'res_id': self.budget_plan_id.id,
                'view_mode': 'form',
                'target': 'current'
            }