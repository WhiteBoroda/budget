# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import UserError


class ProjectProject(models.Model):
    """Расширение проектов для интеграции с бюджетированием и прогнозами"""
    _inherit = 'project.project'

    # Поля для интеграции с продажами и бюджетированием
    is_sales_project = fields.Boolean('Проект продажів',
                                      help="Отметьте, если этот проект связан с прогнозами продаж")

    responsibility_center_id = fields.Many2one(
        'budget.responsibility.center',
        'Центр бюджетної відповідальності',
        help="ЦБО, к которому относится этот проект"
    )

    # Связанные прогнозы
    forecast_ids = fields.One2many('sale.forecast', 'project_id', string='Прогнози продажів')

    # Вычисляемые поля
    forecast_count = fields.Integer('Кількість прогнозів', compute='_compute_forecast_stats')
    total_forecast_amount = fields.Monetary('Сума прогнозів', compute='_compute_forecast_stats',
                                           currency_field='currency_id')

    @api.depends('forecast_ids')
    def _compute_forecast_stats(self):
        """Подсчет статистики по прогнозам"""
        for project in self:
            forecasts = project.forecast_ids.filtered(lambda f: f.state in ['planning', 'review', 'approved'])
            project.forecast_count = len(forecasts)
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
                'default_forecast_scope': 'project',
                'default_cbo_id': self.responsibility_center_id.id if self.responsibility_center_id else False,
                'default_company_id': self.company_id.id if self.company_id else False,
            }
        }

    def action_create_forecast(self):
        """Быстрое создание прогноза для проекта"""
        if not self.is_sales_project:
            raise UserError('Можна створювати прогнози тільки для проектів продажів. Спочатку позначте проект як "Проект продажів".')

        return {
            'type': 'ir.actions.act_window',
            'name': 'Створити прогноз',
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