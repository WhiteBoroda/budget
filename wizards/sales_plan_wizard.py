# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import ValidationError, UserError


class SalesPlanWizard(models.TransientModel):
    """Майстер створення прогнозу продажів"""
    _name = 'sales.plan.wizard'
    _description = 'Майстер створення прогнозу продажів'

    period_id = fields.Many2one('budget.period', 'Період', required=True)
    company_id = fields.Many2one('res.company', 'Підприємство', required=True, default=lambda self: self.env.company)
    base_period_id = fields.Many2one('budget.period', 'Базовий період',
                                     domain="[('company_id', '=', company_id), ('id', '!=', period_id)]")
    growth_rate = fields.Float('Темп росту, %', default=0.0)
    copy_previous = fields.Boolean('Копіювати з попереднього періоду', default=True)

    # Параметри прогнозу
    forecast_scope = fields.Selection([
        ('team', 'Команда продажів'),
        ('cbo', 'ЦБО (кластер/бренд/напрямок)'),
        ('project', 'Проект'),
        ('combined', 'Комбінований')
    ], 'Область прогнозування', required=True, default='team')

    # ИСПРАВЛЕНО для Odoo 17: убираем states из полей
    team_id = fields.Many2one('crm.team', 'Команда продажів',
                              domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]")
    cbo_id = fields.Many2one('budget.responsibility.center', 'ЦБО',
                             domain="[('company_ids', 'in', [company_id])]")
    project_id = fields.Many2one('project.project', 'Проект',
                                 domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]")

    product_category_ids = fields.Many2many('product.category', string='Категорії товарів')

    # Додаткові параметри
    channel = fields.Selection([
        ('direct', 'Прямі продажі'),
        ('retail', 'Роздрібна мережа'),
        ('wholesale', 'Оптові продажі'),
        ('online', 'Онлайн'),
        ('partner', 'Партнерський канал'),
        ('export', 'Експорт'),
        ('b2b', 'B2B'),
        ('b2c', 'B2C'),
        ('other', 'Інше')
    ], 'Канал продажів', default='direct')

    customer_segment = fields.Selection([
        ('new', 'Нові клієнти'),
        ('existing', 'Існуючі клієнти'),
        ('vip', 'VIP клієнти'),
        ('corporate', 'Корпоративні'),
        ('retail', 'Роздрібні'),
        ('government', 'Державні')
    ], 'Сегмент клієнтів', default='existing')

    # Географічні параметри
    country_id = fields.Many2one('res.country', 'Країна')
    state_id = fields.Many2one('res.country.state', 'Область/Штат')

    # ДОБАВЛЕНО для Odoo 17: computed поля вместо attrs
    @api.depends('forecast_scope')
    def _compute_required_fields(self):
        """Определяет какие поля обязательны в зависимости от области прогнозирования"""
        for wizard in self:
            wizard.team_required = wizard.forecast_scope in ['team', 'combined']
            wizard.cbo_required = wizard.forecast_scope in ['cbo', 'combined']
            wizard.project_required = wizard.forecast_scope in ['project', 'combined']

    team_required = fields.Boolean('Команда обов\'язкова', compute='_compute_required_fields')
    cbo_required = fields.Boolean('ЦБО обов\'язково', compute='_compute_required_fields')
    project_required = fields.Boolean('Проект обов\'язковий', compute='_compute_required_fields')

    @api.depends('forecast_scope')
    def _compute_field_visibility(self):
        """Определяет видимость полей в зависимости от области прогнозирования"""
        for wizard in self:
            wizard.show_team = wizard.forecast_scope in ['team', 'combined']
            wizard.show_cbo = wizard.forecast_scope in ['cbo', 'combined']
            wizard.show_project = wizard.forecast_scope in ['project', 'combined']

    show_team = fields.Boolean('Показати команду', compute='_compute_field_visibility')
    show_cbo = fields.Boolean('Показати ЦБО', compute='_compute_field_visibility')
    show_project = fields.Boolean('Показати проект', compute='_compute_field_visibility')

    @api.onchange('company_id')
    def _onchange_company_id(self):
        """Очистка полів при зміні компанії"""
        if self.company_id:
            # Очищаємо поля що залежать від компанії
            self.period_id = False
            self.base_period_id = False
            self.team_id = False
            self.cbo_id = False
            self.project_id = False

    @api.onchange('forecast_scope')
    def _onchange_forecast_scope(self):
        """Очистка полів при зміні області прогнозування"""
        if self.forecast_scope == 'team':
            self.cbo_id = False
            self.project_id = False
        elif self.forecast_scope == 'cbo':
            self.team_id = False
            self.project_id = False
        elif self.forecast_scope == 'project':
            self.team_id = False
            self.cbo_id = False

    @api.constrains('forecast_scope', 'team_id', 'cbo_id', 'project_id')
    def _check_forecast_scope(self):
        """Перевірка правильності заповнення області прогнозування"""
        for record in self:
            if record.forecast_scope == 'team' and not record.team_id:
                raise ValidationError('Для прогнозу команди потрібно вказати команду продажів')
            elif record.forecast_scope == 'cbo' and not record.cbo_id:
                raise ValidationError('Для прогнозу ЦБО потрібно вказати ЦБО')
            elif record.forecast_scope == 'project' and not record.project_id:
                raise ValidationError('Для прогнозу проекту потрібно вказати проект')
            elif record.forecast_scope == 'combined':
                if not any([record.team_id, record.cbo_id, record.project_id]):
                    raise ValidationError('Для комбінованого прогнозу потрібно вказати хоча б одну область')

    def action_create_plan(self):
        """Створення прогнозу продажів"""
        # Перевіряємо чи не існує вже прогноз
        domain = [
            ('period_id', '=', self.period_id.id),
            ('company_id', '=', self.company_id.id),
        ]

        # Додаємо специфічні умови в залежності від області
        if self.forecast_scope == 'team' and self.team_id:
            domain.append(('team_id', '=', self.team_id.id))
        elif self.forecast_scope == 'cbo' and self.cbo_id:
            domain.append(('cbo_id', '=', self.cbo_id.id))
        elif self.forecast_scope == 'project' and self.project_id:
            domain.append(('project_id', '=', self.project_id.id))

        existing_forecasts = self.env['sale.forecast'].search(domain)

        if existing_forecasts:
            raise UserError(f'Прогноз для цього періоду та області вже існує: {existing_forecasts[0].display_name}')

        # Підготовка даних для створення прогнозу
        forecast_vals = {
            'period_id': self.period_id.id,
            'company_id': self.company_id.id,
            'channel': self.channel,
            'customer_segment': self.customer_segment,
            'country_id': self.country_id.id if self.country_id else False,
            'state_id': self.state_id.id if self.state_id else False,
            'user_id': self.env.user.id,
            'forecast_base': 'manual' if not self.copy_previous else 'historical',
            'state': 'draft',
        }

        # Додаємо специфічні поля
        if self.team_id:
            forecast_vals['team_id'] = self.team_id.id
        if self.cbo_id:
            forecast_vals['cbo_id'] = self.cbo_id.id
        if self.project_id:
            forecast_vals['project_id'] = self.project_id.id

        # Створюємо прогноз
        forecast = self.env['sale.forecast'].create(forecast_vals)

        # Копіюємо дані з попереднього періоду, якщо потрібно
        if self.copy_previous and self.base_period_id:
            self._copy_from_previous_period(forecast)
        elif self.copy_previous:
            # Знаходимо попередній період автоматично
            previous_period = self._find_previous_period()
            if previous_period:
                self._copy_from_previous_period(forecast, previous_period)

        # Додаємо лінії прогнозу на основі категорій товарів
        if self.product_category_ids:
            self._create_forecast_lines_by_categories(forecast)

        # Повертаємо action для відкриття створеного прогнозу
        return {
            'type': 'ir.actions.act_window',
            'name': 'Створений прогноз продажів',
            'res_model': 'sale.forecast',
            'res_id': forecast.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def _find_previous_period(self):
        """Знаходження попереднього періоду"""
        previous_period = self.env['budget.period'].search([
            ('company_id', '=', self.company_id.id),
            ('date_end', '<', self.period_id.date_start),
            ('state', 'in', ['planning', 'approved', 'closed'])
        ], order='date_end desc', limit=1)

        return previous_period

    def _copy_from_previous_period(self, forecast, previous_period=None):
        """Копіювання даних з попереднього періоду"""
        source_period = previous_period or self.base_period_id

        if not source_period:
            return

        # Знаходимо прогноз з попереднього періоду
        domain = [
            ('period_id', '=', source_period.id),
            ('company_id', '=', self.company_id.id),
        ]

        if self.team_id:
            domain.append(('team_id', '=', self.team_id.id))
        if self.cbo_id:
            domain.append(('cbo_id', '=', self.cbo_id.id))
        if self.project_id:
            domain.append(('project_id', '=', self.project_id.id))

        source_forecast = self.env['sale.forecast'].search(domain, limit=1)

        if not source_forecast:
            return

        # Коефіцієнт росту
        growth_factor = 1 + (self.growth_rate / 100)

        # Копіюємо лінії прогнозу
        for source_line in source_forecast.forecast_line_ids:
            line_vals = {
                'forecast_id': forecast.id,
                'product_id': source_line.product_id.id if source_line.product_id else False,
                'product_category_id': source_line.product_category_id.id if source_line.product_category_id else False,
                'description': source_line.description,
                'forecast_qty': source_line.forecast_qty * growth_factor,
                'forecast_price': source_line.forecast_price,
                'probability': source_line.probability,
                'expected_date': source_line.expected_date,
                'sales_stage': source_line.sales_stage,
                'partner_category': source_line.partner_category,
                'region': source_line.region,
                'notes': f'Скопійовано з {source_period.name}' + (
                    f' з ростом {self.growth_rate}%' if self.growth_rate else ''),
            }

            self.env['sale.forecast.line'].create(line_vals)

    def _create_forecast_lines_by_categories(self, forecast):
        """Створення ліній прогнозу на основі категорій товарів"""
        for category in self.product_category_ids:
            # Знаходимо товари в категорії
            products = self.env['product.product'].search([
                ('categ_id', 'child_of', category.id),
                ('sale_ok', '=', True),
                ('active', '=', True)
            ], limit=10)  # Обмежуємо кількість для прикладу

            for product in products:
                line_vals = {
                    'forecast_id': forecast.id,
                    'product_id': product.id,
                    'product_category_id': category.id,
                    'description': product.name,
                    'forecast_qty': 1.0,  # Значення за замовчуванням
                    'forecast_price': product.list_price or 0.0,
                    'probability': 50.0,  # Значення за замовчуванням
                    'sales_stage': 'opportunity',
                    'partner_category': 'existing',
                    'notes': f'Автоматично створено для категорії {category.name}',
                }

                self.env['sale.forecast.line'].create(line_vals)

    def action_preview_plan(self):
        """Попередній перегляд плану без створення"""
        # Тут можна реалізувати логіку попереднього перегляду
        # Наприклад, показати які дані будуть скопійовані

        preview_data = {
            'period': self.period_id.name,
            'scope': dict(self._fields['forecast_scope'].selection)[self.forecast_scope],
            'growth_rate': self.growth_rate,
        }

        if self.copy_previous:
            base_period = self.base_period_id or self._find_previous_period()
            if base_period:
                preview_data['base_period'] = base_period.name

        # Повертаємо wizard для відображення preview
        return {
            'type': 'ir.actions.act_window',
            'name': 'Попередній перегляд плану',
            'res_model': 'sales.plan.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'context': {'preview_mode': True, 'preview_data': preview_data}
        }