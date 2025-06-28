# -*- coding: utf-8 -*-

from odoo import models, fields, api


class CrmTeam(models.Model):
    """Расширение команд продаж для интеграции с ЦБО"""
    _inherit = 'crm.team'

    # Связь с ЦБО
    responsibility_center_id = fields.Many2one(
        'budget.responsibility.center',
        'Центр бюджетної відповідальності',
        help="ЦБО, до якого належить ця команда продажів"
    )

    # Настройки прогнозирования
    default_forecast_channel = fields.Selection([
        ('direct', 'Прямі продажі'),
        ('retail', 'Роздрібна мережа'),
        ('wholesale', 'Оптові продажі'),
        ('online', 'Онлайн'),
        ('partner', 'Партнерський канал'),
        ('export', 'Експорт'),
        ('b2b', 'B2B'),
        ('b2c', 'B2C'),
        ('other', 'Інше')
    ], 'Канал продажів за замовчуванням', default='direct')

    default_customer_segment = fields.Selection([
        ('new', 'Нові клієнти'),
        ('existing', 'Існуючі клієнти'),
        ('vip', 'VIP клієнти'),
        ('corporate', 'Корпоративні'),
        ('retail', 'Роздрібні'),
        ('government', 'Державні')
    ], 'Сегмент клієнтів за замовчуванням', default='existing')

    # Настройки бюджетирования
    budget_responsible_user_id = fields.Many2one('res.users', 'Ответственный за бюджет команды')
    auto_create_forecasts = fields.Boolean('Автоматически создавать прогнозы',
                                           help="Автоматически создавать прогнозы для новых периодов")

    # Вычисляемые поля для аналитики
    forecast_count = fields.Integer('Кількість прогнозів', compute='_compute_forecast_count')
    active_forecasts_count = fields.Integer('Активних прогнозів', compute='_compute_forecast_count')

    # Связь с прогнозами
    forecast_ids = fields.One2many('sale.forecast', 'team_id', string='Прогнозы продаж')

    @api.depends('forecast_ids')
    def _compute_forecast_count(self):
        """Подсчет количества прогнозов команды"""
        for team in self:
            team.forecast_count = len(team.forecast_ids)
            team.active_forecasts_count = len(team.forecast_ids.filtered(
                lambda f: f.state in ['draft', 'planning', 'review', 'approved']
            ))

    def action_view_forecasts(self):
        """Открыть прогнозы команды"""
        return {
            'type': 'ir.actions.act_window',
            'name': f'Прогнози команди {self.name}',
            'res_model': 'sale.forecast',
            'view_mode': 'kanban,tree,form',
            'domain': [('team_id', '=', self.id)],
            'context': {
                'default_team_id': self.id,
                'default_channel': self.default_forecast_channel,
                'default_customer_segment': self.default_customer_segment,
            }
        }

    def action_create_forecast(self):
        """Быстрое создание прогноза для команды"""
        return {
            'type': 'ir.actions.act_window',
            'name': 'Створити прогноз',
            'res_model': 'sales.plan.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_team_id': self.id,
                'default_forecast_scope': 'team',
                'default_channel': self.default_forecast_channel,
                'default_customer_segment': self.default_customer_segment,
                'default_cbo_id': self.responsibility_center_id.id if self.responsibility_center_id else False,
            }
        }