# -*- coding: utf-8 -*-

from odoo import models, fields, api


class ResUsers(models.Model):
    """Расширение модели пользователей для интеграции с бюджетированием"""
    _inherit = 'res.users'

    # Связь с ЦБО
    responsible_cbo_ids = fields.One2many('budget.responsibility.center', 'responsible_user_id',
                                          string='ЦБО под ответственностью')
    approver_cbo_ids = fields.One2many('budget.responsibility.center', 'approver_user_id',
                                       string='ЦБО для утверждения')

    # Команды продаж (упрощенный способ получения команд)
    @api.model
    def get_user_sales_teams(self):
        """Получить команды продаж пользователя"""
        teams = self.env['crm.team'].search([('member_ids', 'in', [self.id])])
        return teams

    def _get_sales_teams_domain(self):
        """Домен для команд продаж пользователя"""
        teams = self.get_user_sales_teams()
        return [('id', 'in', teams.ids)]


class CrmTeam(models.Model):
    """Расширение команд продаж для интеграции с бюджетированием"""
    _inherit = 'crm.team'

    # Связь с прогнозами продаж
    forecast_ids = fields.One2many('sale.forecast', 'team_id', string='Прогнозы продаж')
    forecast_count = fields.Integer('Количество прогнозов', compute='_compute_forecast_count')

    # Настройки бюджетирования
    budget_responsible_user_id = fields.Many2one('res.users', 'Ответственный за бюджет команды')
    auto_create_forecasts = fields.Boolean('Автоматически создавать прогнозы',
                                           help="Автоматически создавать прогнозы для новых периодов")

    @api.depends('forecast_ids')
    def _compute_forecast_count(self):
        for team in self:
            team.forecast_count = len(team.forecast_ids)

    def action_view_forecasts(self):
        """Просмотр прогнозов команды"""
        return {
            'type': 'ir.actions.act_window',
            'name': f'Прогнозы команды {self.name}',
            'res_model': 'sale.forecast',
            'view_mode': 'kanban,tree,form',
            'domain': [('team_id', '=', self.id)],
            'context': {'default_team_id': self.id},
        }