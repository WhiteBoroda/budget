# -*- coding: utf-8 -*-

from odoo import models, fields, api


class ProjectProject(models.Model):
    """Расширение проектов для интеграции с прогнозами продаж"""
    _inherit = 'project.project'

    # Связь с ЦБО
    responsibility_center_id = fields.Many2one(
        'budget.responsibility.center',
        'Центр бюджетної відповідальності',
        help="ЦБО, до якого належить цей проект"
    )

    # Настройки продаж
    is_sales_project = fields.Boolean(
        'Проект продажів',
        help="Цей проект пов'язаний з прогнозуванням продажів"
    )

    # Вычисляемые поля
    forecast_count = fields.Integer('Кількість прогнозів', compute='_compute_forecast_count')
    total_forecast_amount = fields.Monetary('Загальний прогноз', compute='_compute_forecast_totals')

    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)

    @api.depends('name')
    def _compute_forecast_count(self):
        """Подсчет количества прогнозов проекта"""
        for project in self:
            forecasts = self.env['sale.forecast'].search([('project_id', '=', project.id)])
            project.forecast_count = len(forecasts)

    @api.depends('name')
    def _compute_forecast_totals(self):
        """Подсчет общих сумм прогнозов"""
        for project in self:
            forecasts = self.env['sale.forecast'].search([
                ('project_id', '=', project.id),
                ('state', 'in', ['approved', 'locked'])
            ])
            project.total_forecast_amount = sum(forecasts.mapped('total_forecast_amount'))

    def action_view_forecasts(self):
        """Открыть прогнозы проекта"""
        return {
            'type': 'ir.actions.act_window',
            'name': f'Прогнози проекту {self.name}',
            'res_model': 'sale.forecast',
            'view_mode': 'kanban,tree,form',
            'domain': [('project_id', '=', self.id)],
            'context': {
                'default_project_id': self.id,
                'default_cbo_id': self.responsibility_center_id.id if self.responsibility_center_id else False,
                'default_forecast_scope': 'project',
            }
        }

    def action_create_forecast(self):
        """Быстрое создание прогноза для проекта"""
        return {
            'type': 'ir.actions.act_window',
            'name': 'Створити прогноз для проекту',
            'res_model': 'sales.plan.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_project_id': self.id,
                'default_forecast_scope': 'project',
                'default_cbo_id': self.responsibility_center_id.id if self.responsibility_center_id else False,
                'default_company_id': self.company_id.id if self.company_id else False,
            }
        }

    @api.onchange('is_sales_project')
    def _onchange_is_sales_project(self):
        """При включении флага продажного проекта предлагаем создать прогноз"""
        if self.is_sales_project and not self.forecast_count:
            return {
                'warning': {
                    'title': 'Створення прогнозу',
                    'message': 'Цей проект позначено як проект продажів. Рекомендуємо створити прогноз продажів для цього проекту.'
                }
            }