# -*- coding: utf-8 -*-

from odoo import models, fields, api


class CrmTeam(models.Model):
    """Розширення команд продаж для інтеграції з ЦБО - ВИПРАВЛЕНА ВЕРСІЯ"""
    _inherit = 'crm.team'

    # Зв'язок з ЦБО
    responsibility_center_id = fields.Many2one(
        'budget.responsibility.center',
        'Центр бюджетної відповідальності',
        help="ЦБО, до якого належить ця команда продажів",
        ondelete='set null'
    )

    # Налаштування прогнозування
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

    # Налаштування бюджетування
    budget_responsible_user_id = fields.Many2one(
        'res.users',
        'Відповідальний за бюджет команди',
        help="Користувач, відповідальний за бюджетне планування цієї команди"
    )

    auto_create_forecasts = fields.Boolean(
        'Автоматично створювати прогнози',
        help="Автоматично створювати прогнози для нових періодів",
        default=False
    )

    # Вичисляємі поля для аналітики
    forecast_count = fields.Integer(
        'Кількість прогнозів',
        compute='_compute_forecast_count',
        help="Загальна кількість прогнозів для цієї команди"
    )

    active_forecasts_count = fields.Integer(
        'Активних прогнозів',
        compute='_compute_forecast_count',
        help="Кількість активних прогнозів (не архівних)"
    )

    # Зв'язок з прогнозами - ВИПРАВЛЕНО
    forecast_ids = fields.One2many(
        'sale.forecast',
        'team_id',
        string='Прогнози продаж',
        help="Всі прогнози продажів цієї команди"
    )

    @api.depends('forecast_ids', 'forecast_ids.state')
    def _compute_forecast_count(self):
        """Підрахунок кількості прогнозів команди"""
        for team in self:
            all_forecasts = team.forecast_ids
            team.forecast_count = len(all_forecasts)
            team.active_forecasts_count = len(all_forecasts.filtered(
                lambda f: f.state in ['draft', 'planning', 'review', 'approved']
            ))

    def action_view_forecasts(self):
        """Відкрити прогнози команди"""
        self.ensure_one()
        action = {
            'type': 'ir.actions.act_window',
            'name': f'Прогнози команди {self.name}',
            'res_model': 'sale.forecast',
            'view_mode': 'kanban,tree,form',
            'domain': [('team_id', '=', self.id)],
            'context': {
                'default_team_id': self.id,
                'default_channel': self.default_forecast_channel,
                'default_customer_segment': self.default_customer_segment,
                'default_cbo_id': self.responsibility_center_id.id if self.responsibility_center_id else False,
                'default_company_id': self.company_id.id if self.company_id else False,
            }
        }

        # Якщо є тільки один прогноз, відкриваємо його напряму
        if len(self.forecast_ids) == 1:
            action.update({
                'res_id': self.forecast_ids.id,
                'view_mode': 'form'
            })

        return action

    def action_create_forecast(self):
        """Швидке створення прогнозу для команди"""
        self.ensure_one()

        # Знаходимо поточний період планування
        current_period = self.env['budget.period'].search([
            ('date_start', '<=', fields.Date.today()),
            ('date_end', '>=', fields.Date.today()),
            ('state', 'in', ['draft', 'planning'])
        ], limit=1)

        if not current_period:
            # Якщо немає поточного, беремо найближчий майбутній
            current_period = self.env['budget.period'].search([
                ('date_start', '>', fields.Date.today()),
                ('state', 'in', ['draft', 'planning'])
            ], order='date_start asc', limit=1)

        if not current_period:
            # Якщо періодів немає, відкриваємо майстер створення
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
                    'default_company_id': self.company_id.id if self.company_id else False,
                }
            }

        # Перевіряємо, чи не існує вже прогноз для цього періоду
        existing_forecast = self.env['sale.forecast'].search([
            ('team_id', '=', self.id),
            ('period_id', '=', current_period.id)
        ], limit=1)

        if existing_forecast:
            # Відкриваємо існуючий прогноз
            return {
                'type': 'ir.actions.act_window',
                'name': f'Прогноз команди {self.name}',
                'res_model': 'sale.forecast',
                'res_id': existing_forecast.id,
                'view_mode': 'form',
                'target': 'current',
            }

        # Створюємо новий прогноз
        forecast_vals = {
            'period_id': current_period.id,
            'team_id': self.id,
            'user_id': self.env.user.id,
            'channel': self.default_forecast_channel or 'direct',
            'customer_segment': self.default_customer_segment or 'existing',
            'forecast_base': 'manual',
            'state': 'draft',
            'company_id': self.company_id.id if self.company_id else self.env.company.id,
        }

        # Додаємо ЦБО, якщо є
        if self.responsibility_center_id:
            forecast_vals['cbo_id'] = self.responsibility_center_id.id

        # Додаємо відповідального за бюджет, якщо є
        if self.budget_responsible_user_id:
            forecast_vals['user_id'] = self.budget_responsible_user_id.id

        forecast = self.env['sale.forecast'].create(forecast_vals)

        return {
            'type': 'ir.actions.act_window',
            'name': f'Новий прогноз для команди {self.name}',
            'res_model': 'sale.forecast',
            'res_id': forecast.id,
            'view_mode': 'form',
            'target': 'current',
        }

    @api.model
    def create_auto_forecasts(self):
        """Автоматичне створення прогнозів для команд (викликається з cron)"""
        # Знаходимо команди з увімкненим автоматичним створенням
        teams = self.search([('auto_create_forecasts', '=', True)])

        # Знаходимо нові періоди, для яких потрібно створити прогнози
        new_periods = self.env['budget.period'].search([
            ('state', '=', 'planning'),
            ('date_start', '>=', fields.Date.today())
        ])

        created_forecasts = 0

        for team in teams:
            for period in new_periods:
                # Перевіряємо, чи не існує вже прогноз
                existing = self.env['sale.forecast'].search([
                    ('team_id', '=', team.id),
                    ('period_id', '=', period.id)
                ])

                if not existing:
                    # Створюємо прогноз
                    self.env['sale.forecast'].create({
                        'period_id': period.id,
                        'team_id': team.id,
                        'user_id': team.budget_responsible_user_id.id or team.user_id.id,
                        'channel': team.default_forecast_channel or 'direct',
                        'customer_segment': team.default_customer_segment or 'existing',
                        'cbo_id': team.responsibility_center_id.id if team.responsibility_center_id else False,
                        'forecast_base': 'manual',
                        'state': 'draft',
                        'company_id': team.company_id.id if team.company_id else self.env.company.id,
                    })
                    created_forecasts += 1

        return created_forecasts

    def action_budget_dashboard(self):
        """Відкрити панель бюджетування для команди"""
        self.ensure_one()

        if not self.responsibility_center_id:
            from odoo.exceptions import UserError
            raise UserError('Для доступу до панелі бюджетування потрібно призначити ЦБО для команди')

        return {
            'type': 'ir.actions.act_window',
            'name': f'Бюджетування - {self.name}',
            'res_model': 'budget.dashboard',
            'view_mode': 'kanban,form',
            'domain': [('company_id', '=', self.company_id.id if self.company_id else self.env.company.id)],
            'context': {
                'default_company_id': self.company_id.id if self.company_id else self.env.company.id,
                'team_filter': self.id,
            }
        }

    @api.onchange('responsibility_center_id')
    def _onchange_responsibility_center_id(self):
        """При зміні ЦБО, налаштовуємо відповідального за бюджет"""
        if self.responsibility_center_id and self.responsibility_center_id.responsible_user_id:
            self.budget_responsible_user_id = self.responsibility_center_id.responsible_user_id