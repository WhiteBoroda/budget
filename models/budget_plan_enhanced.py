# -*- coding: utf-8 -*-
# Додаткові методи для моделі budget.plan - СУМІСНІ З ODOO 17

from odoo import models, api, fields, _
from odoo.exceptions import ValidationError, UserError
from datetime import datetime, timedelta
import json


class BudgetPlanExtended(models.Model):
    """Розширення моделі бюджетного плану для роботи з віджетами"""
    _inherit = 'budget.plan'

    @api.model
    def get_dashboard_data(self):
        """Отримання даних для dashboard віджета - ODOO 17"""
        try:
            # Базові запити з оптимізацією
            domain_base = [('company_id', 'in', self.env.companies.ids)]

            # Підрахунок бюджетів по статусах
            budgets_by_state = self.read_group(
                domain=domain_base,
                fields=['state'],
                groupby=['state']
            )

            state_counts = {item['state']: item['state_count'] for item in budgets_by_state}

            # Фінансові показники
            financial_data = self.search_read(
                domain=domain_base + [('state', 'in', ['approved', 'executed'])],
                fields=['planned_amount', 'actual_amount', 'available_amount', 'currency_id']
            )

            # Агрегація сум (конвертація в основну валюту)
            company_currency = self.env.company.currency_id
            total_planned = 0.0
            total_actual = 0.0
            total_available = 0.0

            for budget in financial_data:
                currency = self.env['res.currency'].browse(budget['currency_id'][0]) if budget[
                    'currency_id'] else company_currency

                planned = currency._convert(
                    budget['planned_amount'] or 0.0,
                    company_currency,
                    self.env.company,
                    fields.Date.today()
                )
                actual = currency._convert(
                    budget['actual_amount'] or 0.0,
                    company_currency,
                    self.env.company,
                    fields.Date.today()
                )
                available = currency._convert(
                    budget['available_amount'] or 0.0,
                    company_currency,
                    self.env.company,
                    fields.Date.today()
                )

                total_planned += planned
                total_actual += actual
                total_available += available

            # Прострочені бюджети
            today = fields.Date.today()
            overdue_count = self.search_count([
                                                  ('state', '=', 'planning'),
                                                  ('period_id.date_end', '<', today)
                                              ] + domain_base)

            return {
                'total_budgets': sum(state_counts.values()),
                'approved_budgets': state_counts.get('approved', 0),
                'pending_budgets': state_counts.get('planning', 0) + state_counts.get('coordination', 0),
                'overdue_budgets': overdue_count,
                'planned_amount': total_planned,
                'actual_amount': total_actual,
                'available_amount': total_available,
                'currency_symbol': company_currency.symbol,
                'last_updated': fields.Datetime.now().isoformat()
            }

        except Exception as e:
            # Логування помилки
            _logger = self.env['ir.logging'].sudo()
            _logger.create({
                'name': 'budget.dashboard.error',
                'level': 'ERROR',
                'message': f'Dashboard data error: {str(e)}',
                'path': 'budget_plan.get_dashboard_data',
                'func': 'get_dashboard_data',
                'line': '0'
            })

            # Повертаємо значення за замовчуванням
            return {
                'total_budgets': 0,
                'approved_budgets': 0,
                'pending_budgets': 0,
                'overdue_budgets': 0,
                'planned_amount': 0.0,
                'actual_amount': 0.0,
                'available_amount': 0.0,
                'currency_symbol': self.env.company.currency_id.symbol,
                'last_updated': fields.Datetime.now().isoformat(),
                'error': True
            }

    @api.model
    def get_budget_analytics(self, period_ids=None, cbo_ids=None):
        """Аналітика бюджетів для розширених віджетів"""
        domain = [('company_id', 'in', self.env.companies.ids)]

        if period_ids:
            domain.append(('period_id', 'in', period_ids))
        if cbo_ids:
            domain.append(('cbo_id', 'in', cbo_ids))

        # Аналітика по періодах
        period_analytics = self.read_group(
            domain=domain,
            fields=['period_id', 'planned_amount', 'actual_amount'],
            groupby=['period_id']
        )

        # Аналітика по ЦБО
        cbo_analytics = self.read_group(
            domain=domain,
            fields=['cbo_id', 'planned_amount', 'actual_amount'],
            groupby=['cbo_id']
        )

        # Аналітика по типах бюджетів
        type_analytics = self.read_group(
            domain=domain,
            fields=['budget_type_id', 'planned_amount', 'actual_amount'],
            groupby=['budget_type_id']
        )

        # Тренди виконання
        execution_trend = []
        for item in period_analytics:
            planned = item['planned_amount'] or 0.0
            actual = item['actual_amount'] or 0.0
            execution_rate = (actual / planned * 100) if planned > 0 else 0.0

            execution_trend.append({
                'period': item['period_id'][1] if item['period_id'] else 'Невизначений',
                'planned': planned,
                'actual': actual,
                'execution_rate': execution_rate
            })

        return {
            'period_analytics': period_analytics,
            'cbo_analytics': cbo_analytics,
            'type_analytics': type_analytics,
            'execution_trend': execution_trend,
            'summary': {
                'total_periods': len(period_analytics),
                'total_cbos': len(cbo_analytics),
                'avg_execution_rate': sum(item['execution_rate'] for item in execution_trend) / len(
                    execution_trend) if execution_trend else 0
            }
        }

    def action_create_child_budget(self):
        """Створення дочірнього бюджету"""
        self.ensure_one()

        return {
            'name': f'Дочірній бюджет для {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'budget.plan',
            'view_mode': 'form',
            'context': {
                'default_parent_budget_id': self.id,
                'default_cbo_id': self.cbo_id.id,
                'default_period_id': self.period_id.id,
                'default_budget_type_id': self.budget_type_id.id,
                'default_name': f'Дочірній бюджет - {self.name}',
            },
            'target': 'new'
        }

    def action_view_cbo_structure(self):
        """Перегляд структури ЦБО для цього бюджету"""
        self.ensure_one()

        return {
            'name': f'Структура ЦБО - {self.cbo_id.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'budget.responsibility.center',
            'view_mode': 'tree,form',
            'domain': [
                '|',
                ('id', 'child_of', self.cbo_id.id),
                ('id', '=', self.cbo_id.id)
            ],
            'context': {
                'search_default_filter_active': 1,
                'tree_view_ref': 'budget.view_responsibility_center_hierarchy_tree'
            }
        }

    @api.model
    def get_budget_summary_for_cbo(self, cbo_id):
        """Отримання зведення бюджетів для конкретного ЦБО"""
        if not cbo_id:
            return {}

        cbo = self.env['budget.responsibility.center'].browse(cbo_id)
        if not cbo.exists():
            return {}

        # Отримуємо всіх нащадків ЦБО
        all_cbo_ids = self.env['budget.responsibility.center'].search([
            ('id', 'child_of', cbo_id)
        ]).ids

        # Бюджети для всієї ієрархії
        budgets = self.search([
            ('cbo_id', 'in', all_cbo_ids),
            ('state', 'in', ['approved', 'executed'])
        ])

        summary = {
            'cbo_name': cbo.name,
            'total_budgets': len(budgets),
            'total_planned': sum(budgets.mapped('planned_amount')),
            'total_actual': sum(budgets.mapped('actual_amount')),
            'total_available': sum(budgets.mapped('available_amount')),
            'execution_rate': 0.0,
            'by_period': {},
            'by_type': {}
        }

        # Розрахунок рівня виконання
        if summary['total_planned'] > 0:
            summary['execution_rate'] = (summary['total_actual'] / summary['total_planned']) * 100

        # Групування по періодах
        for budget in budgets:
            period_name = budget.period_id.name
            if period_name not in summary['by_period']:
                summary['by_period'][period_name] = {
                    'planned': 0.0,
                    'actual': 0.0,
                    'count': 0
                }

            summary['by_period'][period_name]['planned'] += budget.planned_amount
            summary['by_period'][period_name]['actual'] += budget.actual_amount
            summary['by_period'][period_name]['count'] += 1

        # Групування по типах
        for budget in budgets:
            type_name = budget.budget_type_id.name
            if type_name not in summary['by_type']:
                summary['by_type'][type_name] = {
                    'planned': 0.0,
                    'actual': 0.0,
                    'count': 0
                }

            summary['by_type'][type_name]['planned'] += budget.planned_amount
            summary['by_type'][type_name]['actual'] += budget.actual_amount
            summary['by_type'][type_name]['count'] += 1

        return summary

    @api.model
    def get_recent_budgets(self, limit=10):
        """Отримання останніх бюджетів для dashboard"""
        recent_budgets = self.search([
            ('company_id', 'in', self.env.companies.ids)
        ], order='create_date desc', limit=limit)

        result = []
        for budget in recent_budgets:
            result.append({
                'id': budget.id,
                'name': budget.name,
                'cbo_name': budget.cbo_id.name,
                'state': budget.state,
                'planned_amount': budget.planned_amount,
                'execution_rate': budget.execution_rate,
                'create_date': budget.create_date.isoformat() if budget.create_date else None,
                'period_name': budget.period_id.name
            })

        return result

    def action_quick_approve(self):
        """Швидке затвердження бюджету"""
        for budget in self:
            if budget.state in ['planning', 'coordination']:
                budget.write({
                    'state': 'approved',
                    'approved_date': fields.Datetime.now(),
                    'approved_by_id': self.env.user.id
                })

                # Повідомлення учасникам
                budget.message_post(
                    body=f"Бюджет швидко затверджено користувачем {self.env.user.name}",
                    message_type='notification'
                )

        return True

    def action_bulk_operation(self, operation):
        """Масові операції з бюджетами"""
        if operation == 'approve':
            return self.action_quick_approve()
        elif operation == 'archive':
            return self.write({'active': False})
        elif operation == 'activate':
            return self.write({'active': True})
        elif operation == 'reset_to_draft':
            return self.write({'state': 'draft'})
        else:
            raise UserError(f"Невідома операція: {operation}")

    @api.model
    def search_budgets_advanced(self, query, filters=None):
        """Розширений пошук бюджетів"""
        domain = [('company_id', 'in', self.env.companies.ids)]

        # Текстовий пошук
        if query:
            domain.append('|')
            domain.append(('name', 'ilike', query))
            domain.append(('code', 'ilike', query))

        # Додаткові фільтри
        if filters:
            if 'state' in filters:
                domain.append(('state', '=', filters['state']))
            if 'cbo_id' in filters:
                domain.append(('cbo_id', '=', filters['cbo_id']))
            if 'period_id' in filters:
                domain.append(('period_id', '=', filters['period_id']))
            if 'date_from' in filters:
                domain.append(('create_date', '>=', filters['date_from']))
            if 'date_to' in filters:
                domain.append(('create_date', '<=', filters['date_to']))

        return self.search(domain, order='create_date desc')

    @api.model
    def get_budget_kpis(self):
        """Отримання KPI по бюджетах"""
        domain = [
            ('company_id', 'in', self.env.companies.ids),
            ('state', 'in', ['approved', 'executed'])
        ]

        budgets = self.search(domain)

        if not budgets:
            return {}

        total_planned = sum(budgets.mapped('planned_amount'))
        total_actual = sum(budgets.mapped('actual_amount'))

        # Бюджети в межах ліміту (виконання <= 100%)
        within_limit = budgets.filtered(lambda b: b.execution_rate <= 100)

        # Бюджети з перевитратами
        over_budget = budgets.filtered(lambda b: b.execution_rate > 100)

        # Середній рівень виконання
        avg_execution = sum(budgets.mapped('execution_rate')) / len(budgets)

        return {
            'total_budgets': len(budgets),
            'total_planned': total_planned,
            'total_actual': total_actual,
            'overall_execution_rate': (total_actual / total_planned * 100) if total_planned > 0 else 0,
            'avg_execution_rate': avg_execution,
            'within_limit_count': len(within_limit),
            'over_budget_count': len(over_budget),
            'within_limit_percentage': (len(within_limit) / len(budgets) * 100),
            'over_budget_percentage': (len(over_budget) / len(budgets) * 100),
            'best_performing': budgets.sorted('execution_rate')[0].read(['name', 'execution_rate'])[
                0] if budgets else None,
            'worst_performing': budgets.sorted('execution_rate', reverse=True)[0].read(['name', 'execution_rate'])[
                0] if budgets else None
        }