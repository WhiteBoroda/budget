# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import ValidationError, UserError
import logging

_logger = logging.getLogger(__name__)


class SaleForecast(models.Model):
    """Прогноз продажів"""
    _name = 'sale.forecast'
    _description = 'Прогноз продажів'
    _order = 'period_id desc, team_id'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # Автонумерація
    name = fields.Char('Номер', required=True, copy=False, readonly=True, default='/')

    def _compute_display_name(self):
        for record in self:
            if record.team_id and record.period_id and record.channel:
                team_name = record.team_id.name
                period_name = record.period_id.name
                channel_name = dict(record._fields['channel'].selection).get(record.channel, record.channel)
                record.display_name = f"{team_name} - {channel_name} ({period_name})"
            elif record.name and record.name != '/':
                record.display_name = record.name
            else:
                record.display_name = "Новий прогноз"

    display_name = fields.Char('Назва', compute='_compute_display_name', store=True)

    # Основні параметри
    period_id = fields.Many2one('budget.period', 'Період планування', required=True, index=True)
    team_id = fields.Many2one('crm.team', 'Команда продажів', required=True, index=True)
    user_id = fields.Many2one('res.users', 'Відповідальний', required=True,
                              default=lambda self: self.env.user, index=True)

    # Канали та сегменти
    channel = fields.Selection([
        ('direct', 'Прямі продажі'),
        ('retail', 'Роздрібна торгівля'),
        ('wholesale', 'Оптова торгівля'),
        ('online', 'Онлайн продажі'),
        ('partner', 'Через партнерів'),
        ('export', 'Експорт'),
        ('b2b', 'B2B продажі'),
        ('b2c', 'B2C продажі')
    ], 'Канал продажів', required=True, default='direct', index=True)

    customer_segment = fields.Selection([
        ('new', 'Нові клієнти'),
        ('existing', 'Існуючі клієнти'),
        ('vip', 'VIP клієнти'),
        ('corporate', 'Корпоративні клієнти'),
        ('retail', 'Роздрібні клієнти')
    ], 'Сегмент клієнтів', required=True, default='existing')

    # ИСПРАВЛЕНО для Odoo 17: убираем states из поля state
    state = fields.Selection([
        ('draft', 'Чернетка'),
        ('planning', 'Планування'),
        ('review', 'На перевірці'),
        ('approved', 'Затверджений'),
        ('revision', 'Доопрацювання'),
        ('archived', 'Архівний')
    ], 'Статус', default='draft', required=True, tracking=True, index=True)

    # Підходи до прогнозування
    forecast_base = fields.Selection([
        ('manual', 'Ручне планування'),
        ('historical', 'На основі історії'),
        ('market_research', 'Дослідження ринку'),
        ('pipeline', 'На основі воронки продажів'),
        ('mixed', 'Змішаний підхід')
    ], 'Основа прогнозу', required=True, default='manual')

    # ИСПРАВЛЕНО для Odoo 17: убираем states из финансовых полей
    total_forecast_amount = fields.Monetary('Загальна сума прогнозу',
                                            compute='_compute_totals', store=True, currency_field='currency_id')
    total_forecast_qty = fields.Float('Загальна кількість',
                                      compute='_compute_totals', store=True)

    # ДОДАНО: Поля для маржі на рівні прогнозу
    total_margin = fields.Monetary('Загальна маржа', compute='_compute_totals_margin', store=True, currency_field='currency_id')
    margin_percent = fields.Float('Маржинальність, %', compute='_compute_totals_margin', store=True)

    # Середні показники
    avg_deal_size = fields.Monetary('Середній розмір угоди',
                                    compute='_compute_averages', store=True, currency_field='currency_id')
    deals_count = fields.Integer('Кількість угод',
                                 compute='_compute_averages', store=True)

    # Конверсії та ефективність
    conversion_rate = fields.Float('Коефіцієнт конверсії, %',
                                   compute='_compute_conversion', store=True)
    sales_cycle_days = fields.Integer('Тривалість циклу продажів, днів')

    # Інтеграція з проектами та ЦБО
    project_id = fields.Many2one('project.project', 'Проект',
                                 help="Прогноз продажів може бути прив'язаний до конкретного проекту")

    cbo_id = fields.Many2one('budget.responsibility.center', 'ЦБО',
                             help="Центр бюджетної відповідальності, до якого належить прогноз")

    # Географічні параметри
    country_id = fields.Many2one('res.country', 'Країна')
    state_id = fields.Many2one('res.country.state', 'Область/Штат')

    # Організаційні поля
    company_id = fields.Many2one('res.company', 'Підприємство', required=True,
                                 default=lambda self: self.env.company, index=True)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id', readonly=True)

    # Лінії прогнозу
    forecast_line_ids = fields.One2many('sale.forecast.line', 'forecast_id', 'Позиції прогнозу')

    # Дедлайни та дати
    submission_deadline = fields.Date('Крайній термін подання', default=fields.Date.today)
    approved_date = fields.Datetime('Дата затвердження')
    approved_by_id = fields.Many2one('res.users', 'Затверджено')

    # Примітки та обґрунтування
    methodology_notes = fields.Text('Методологія прогнозування')
    market_assumptions = fields.Text('Припущення щодо ринку')
    risk_factors = fields.Text('Фактори ризику')

    notes = fields.Text('Додаткові примітки')

    # Шаблони прогнозів
    template_id = fields.Many2one('sale.forecast.template', 'Шаблон прогнозу')

    # ДОБАВЛЕНО для Odoo 17: computed поля вместо states
    @api.depends('state')
    def _compute_can_edit(self):
        """Определяет можно ли редактировать прогноз"""
        for forecast in self:
            forecast.can_edit = forecast.state in ['draft', 'planning', 'revision']

    can_edit = fields.Boolean('Можна редагувати', compute='_compute_can_edit')

    @api.depends('state')
    def _compute_is_readonly(self):
        """Определяет является ли прогноз только для чтения"""
        for forecast in self:
            forecast.is_readonly = forecast.state in ['approved', 'archived']

    is_readonly = fields.Boolean('Тільки для читання', compute='_compute_is_readonly')

    @api.model
    def create(self, vals_list):
        """Створення прогнозів з підтримкою batch операцій"""
        # Перетворюємо в список якщо переданий словник
        if isinstance(vals_list, dict):
            vals_list = [vals_list]

        # Обробляємо кожен запис
        for vals in vals_list:
            # Автогенерація назви якщо не вказана
            if not vals.get('name'):
                vals['name'] = self._generate_forecast_name(vals)

            # Автогенерація номера з послідовності
            if vals.get('name', '/') == '/':
                vals['name'] = self.env['ir.sequence'].next_by_code('sale.forecast') or 'Новий прогноз'

            # Валідація основних полів
            if not vals.get('period_id'):
                raise ValidationError('Період є обов\'язковим для прогнозу')

            # Встановлення значень за замовчуванням
            if not vals.get('company_id'):
                vals['company_id'] = self.env.company.id

            if not vals.get('user_id'):
                vals['user_id'] = self.env.user.id

            if not vals.get('state'):
                vals['state'] = 'draft'

            # Автоматичне встановлення каналу з команди
            if vals.get('team_id') and not vals.get('channel'):
                team = self.env['crm.team'].browse(vals['team_id'])
                if team.exists() and hasattr(team, 'default_forecast_channel'):
                    vals['channel'] = team.default_forecast_channel or 'direct'

        # Створення записів
        forecasts = super().create(vals_list)

        # Пост-обробка для кожного створеного прогнозу
        for forecast in forecasts:
            # Логування
            self.env['budget.log'].sudo().create({
                'model_name': 'sale.forecast',
                'record_id': forecast.id,
                'action': 'create',
                'description': f'Створено прогноз продажів: {forecast.name}',
                'user_id': self.env.user.id
            })

            # Повідомлення в чаттері
            forecast.message_post(
                body=f"🎯 Створено новий прогноз продажів для періоду {forecast.period_id.name}",
                message_type='notification'
            )

        return forecasts

    def _generate_forecast_name(self, vals):
        """Генерація назви прогнозу"""
        period_name = "Період"
        team_name = "Команда"

        # Отримуємо назву періоду
        if vals.get('period_id'):
            period = self.env['budget.period'].browse(vals['period_id'])
            period_name = period.name if period.exists() else "Період"

        # Отримуємо назву команди або проекту
        if vals.get('team_id'):
            team = self.env['crm.team'].browse(vals['team_id'])
            team_name = team.name if team.exists() else "Команда"
        elif vals.get('project_id'):
            project = self.env['project.project'].browse(vals['project_id'])
            team_name = project.name if project.exists() else "Проект"

        return f"Прогноз {team_name} - {period_name}"

    def _validate_forecast_data(self, vals):
        """Валідація даних прогнозу"""
        # Перевірка періоду
        if vals.get('period_id'):
            period = self.env['budget.period'].browse(vals['period_id'])
            if not period.exists():
                raise ValidationError("Вказаний період не існує")
            if period.state == 'closed':
                raise ValidationError("Неможливо створити прогноз для закритого періоду")

        # Перевірка команди або проекту
        if not vals.get('team_id') and not vals.get('project_id'):
            if vals.get('forecast_scope', 'team') in ['team', 'combined']:
                raise ValidationError("Необхідно вказати команду продажів або проект")

    def _set_default_values(self, vals):
        """Встановлення значень за замовчуванням"""
        # Встановлення компанії за замовчуванням
        if not vals.get('company_id'):
            vals['company_id'] = self.env.company.id

        # Встановлення користувача за замовчуванням
        if not vals.get('user_id'):
            vals['user_id'] = self.env.user.id

        # Встановлення каналу за замовчуванням
        if not vals.get('channel'):
            if vals.get('team_id'):
                team = self.env['crm.team'].browse(vals['team_id'])
                if team.exists() and team.default_forecast_channel:
                    vals['channel'] = team.default_forecast_channel
                else:
                    vals['channel'] = 'direct'

    def _post_create_actions(self):
        """Дії після створення прогнозу"""
        # Логування створення
        _logger.info(f'Створено прогноз продажів: {self.name} (ID: {self.id})')

        # Повідомлення в чаттері
        self.message_post(
            body=f"🎯 Створено новий прогноз продажів для {self.period_id.name}",
            message_type='notification'
        )

        # Автоматичне створення базових ліній (якщо потрібно)
        if not self.forecast_line_ids and hasattr(self, '_create_default_lines'):
            self._create_default_lines()

    @api.depends('forecast_line_ids.forecast_amount')
    def _compute_totals(self):
        """Розрахунок загальних сум"""
        for forecast in self:
            forecast.total_forecast_amount = sum(forecast.forecast_line_ids.mapped('forecast_amount'))


    @api.depends('forecast_line_ids.forecast_amount', 'forecast_line_ids.forecast_qty')
    def _compute_totals(self):
        for record in self:
            record.total_forecast_amount = sum(record.forecast_line_ids.mapped('forecast_amount'))
            record.total_forecast_qty = sum(record.forecast_line_ids.mapped('forecast_qty'))

    @api.depends('forecast_line_ids.forecast_amount', 'forecast_line_ids.margin_percent')
    def _compute_totals_margin(self):
        for record in self:
            total_margin_amount = 0.0
            for line in record.forecast_line_ids:
                total_margin_amount += line.forecast_amount * (line.margin_percent / 100.0)
            record.total_margin = total_margin_amount

            if record.total_forecast_amount:
                record.margin_percent = (record.total_margin / record.total_forecast_amount) * 100
            else:
                record.margin_percent = 0.0

    @api.depends('forecast_line_ids.forecast_amount')
    def _compute_averages(self):
        for record in self:
            lines_count = len(record.forecast_line_ids)
            record.deals_count = lines_count
            if lines_count > 0:
                record.avg_deal_size = record.total_forecast_amount / lines_count
            else:
                record.avg_deal_size = 0.0

    @api.depends('forecast_line_ids.probability')
    def _compute_conversion(self):
        for record in self:
            if record.forecast_line_ids:
                avg_probability = sum(record.forecast_line_ids.mapped('probability')) / len(record.forecast_line_ids)
                record.conversion_rate = avg_probability
            else:
                record.conversion_rate = 0.0

    @api.onchange('team_id')
    def _onchange_team_id(self):
        """Автоматичне заповнення полів на основі команди"""
        if self.team_id:
            self.channel = self.team_id.default_forecast_channel or 'direct'
            self.customer_segment = self.team_id.default_customer_segment or 'existing'
            # Встановлюємо ЦБО з команди, якщо є
            if self.team_id.responsibility_center_id:
                self.cbo_id = self.team_id.responsibility_center_id
            # Встановлюємо відповідального за бюджет команди, якщо є
            if self.team_id.budget_responsible_user_id:
                self.user_id = self.team_id.budget_responsible_user_id

    @api.onchange('template_id')
    def _onchange_template_id(self):
        """Застосування шаблону прогнозу"""
        if self.template_id:
            # Очищуємо існуючі лінії
            self.forecast_line_ids = [(5, 0, 0)]

            # Створюємо нові лінії на основі шаблону
            lines_data = []
            for template_line in self.template_id.line_ids:
                lines_data.append((0, 0, {
                    'product_id': template_line.product_id.id,
                    'product_category_id': template_line.product_category_id.id,
                    'forecast_qty': template_line.default_qty,
                    'forecast_price': template_line.default_price,
                    'probability': template_line.default_probability,
                    'description': template_line.description,
                }))

            self.forecast_line_ids = lines_data
            self.methodology_notes = self.template_id.methodology_notes

    def action_start_planning(self):
        """Початок планування"""
        self.state = 'planning'
        self.message_post(body="Розпочато планування прогнозу")

    def action_submit_review(self):
        """Відправка на перевірку"""
        if not self.forecast_line_ids:
            raise ValidationError('Неможливо відправити порожній прогноз на перевірку!')

        self.state = 'review'
        self.message_post(body="Прогноз відправлено на перевірку")

        # Сповіщення менеджера команди
        if self.team_id.user_id:
            self.activity_schedule(
                'mail.mail_activity_data_todo',
                user_id=self.team_id.user_id.id,
                summary=f'Перевірка прогнозу: {self.display_name}'
            )

    def action_approve(self):
        """Затвердження прогнозу"""
        self.write({
            'state': 'approved',
            'approved_by_id': self.env.user.id,
            'approved_date': fields.Datetime.now(),
        })
        self.message_post(body="Прогноз затверджено")

    def action_request_revision(self):
        """Відправка на доопрацювання"""
        self.state = 'revision'
        self.message_post(body="Прогноз відправлено на доопрацювання")

        # Сповіщення відповідального
        if self.user_id:
            self.activity_schedule(
                'mail.mail_activity_data_todo',
                user_id=self.user_id.id,
                summary=f'Доопрацювання прогнозу: {self.display_name}'
            )

    def action_archive(self):
        """Архівування прогнозу"""
        self.state = 'archived'

    def action_duplicate_forecast(self):
        """Дублювання прогнозу"""
        new_forecast = self.copy({
            'name': '/',
            'state': 'draft',
            'approved_by_id': False,
            'approved_date': False,
        })

        return {
            'type': 'ir.actions.act_window',
            'name': 'Копія прогнозу',
            'res_model': 'sale.forecast',
            'res_id': new_forecast.id,
            'view_mode': 'form',
            'target': 'current'
        }


class SaleForecastLine(models.Model):
    """Лінії прогнозу продажів"""
    _name = 'sale.forecast.line'
    _description = 'Лінії прогнозу продажів'

    forecast_id = fields.Many2one('sale.forecast', 'Прогноз', required=True, ondelete='cascade')

    # Продукт або категорія
    product_id = fields.Many2one('product.product', 'Товар')
    product_category_id = fields.Many2one('product.category', 'Категорія товарів')

    description = fields.Char('Опис', required=True)

    # ИСПРАВЛЕНО для Odoo 17: убираем states из полей
    forecast_qty = fields.Float('Прогнозна кількість', required=True, default=1.0)
    forecast_price = fields.Monetary('Прогнозна ціна', required=True, currency_field='currency_id')
    forecast_amount = fields.Monetary('Прогнозна сума', compute='_compute_forecast_amount',
                                      store=True, currency_field='currency_id')

    # ДОДАНО: Маржа на рівні позиції
    margin_percent = fields.Float('Маржа, %', default=25.0, help="Валова маржа для даної позиції прогнозу")

    # Ймовірність та конверсія
    probability = fields.Float('Ймовірність, %', default=50.0,
                               help="Ймовірність реалізації прогнозу у відсотках")
    weighted_amount = fields.Monetary('Зважена сума', compute='_compute_weighted_amount',
                                      store=True, currency_field='currency_id')

    # Часові рамки
    expected_date = fields.Date('Очікувана дата')
    sales_stage = fields.Selection([
        ('lead', 'Лід'),
        ('opportunity', 'Можливість'),
        ('quotation', 'Пропозиція'),
        ('negotiation', 'Переговори'),
        ('closing', 'Закриття')
    ], 'Стадія продажів', default='opportunity')

    # Клієнтська база
    partner_id = fields.Many2one('res.partner', 'Клієнт')
    partner_category = fields.Selection([
        ('new', 'Новий клієнт'),
        ('existing', 'Існуючий клієнт'),
        ('potential', 'Потенційний клієнт')
    ], 'Категорія клієнта', default='existing')

    # Зв'язок з CRM
    opportunity_id = fields.Many2one('crm.lead', 'Можливість в CRM')

    currency_id = fields.Many2one('res.currency', related='forecast_id.company_id.currency_id', readonly=True)

    # Аналітичні поля
    region = fields.Char('Регіон')
    sales_person_id = fields.Many2one('res.users', 'Менеджер з продажів')

    notes = fields.Text('Примітки')

    # ДОДАНО для Odoo 17: computed поля вместо states
    @api.depends('forecast_id.state')
    def _compute_is_editable(self):
        """Определяет можно ли редактировать строку"""
        for line in self:
            line.is_editable = line.forecast_id.state in ['draft', 'planning', 'revision']

    is_editable = fields.Boolean('Можна редагувати', compute='_compute_is_editable')

    @api.depends('forecast_qty', 'forecast_price')
    def _compute_forecast_amount(self):
        for line in self:
            line.forecast_amount = line.forecast_qty * line.forecast_price

    @api.depends('forecast_amount', 'probability')
    def _compute_weighted_amount(self):
        for line in self:
            line.weighted_amount = line.forecast_amount * (line.probability / 100)

    @api.onchange('product_id')
    def _onchange_product_id(self):
        """Автоматичне заповнення полів на основі товару"""
        if self.product_id:
            self.description = self.product_id.name
            self.forecast_price = self.product_id.list_price
            self.product_category_id = self.product_id.categ_id

    @api.onchange('opportunity_id')
    def _onchange_opportunity_id(self):
        """Підтягування даних з CRM можливості"""
        if self.opportunity_id:
            self.partner_id = self.opportunity_id.partner_id
            self.forecast_amount = self.opportunity_id.expected_revenue
            self.probability = self.opportunity_id.probability
            self.expected_date = self.opportunity_id.date_deadline
            self.description = self.opportunity_id.name or "З CRM можливості"

    @api.model
    def create(self, vals_list):
        """Створення ліній прогнозу з підтримкою batch операцій"""
        if isinstance(vals_list, dict):
            vals_list = [vals_list]

        # Обробка кожного запису
        for vals in vals_list:
            # Валідація обов'язкових полей
            if not vals.get('forecast_id'):
                raise ValidationError('Не вказано прогноз для лінії')

            if not vals.get('description'):
                if vals.get('product_id'):
                    product = self.env['product.product'].browse(vals['product_id'])
                    vals['description'] = product.name if product.exists() else 'Нова позиція'
                else:
                    vals['description'] = 'Нова позиція прогнозу'

            # Встановлення значень за замовчуванням
            if not vals.get('forecast_qty'):
                vals['forecast_qty'] = 1.0

            if not vals.get('probability'):
                vals['probability'] = 50.0

            if not vals.get('sales_stage'):
                vals['sales_stage'] = 'opportunity'

        return super().create(vals_list)


class SaleForecastTemplate(models.Model):
    """Шаблони прогнозів продажів"""
    _name = 'sale.forecast.template'
    _description = 'Шаблон прогнозу продажів'

    name = fields.Char('Назва шаблону', required=True)
    description = fields.Text('Опис')

    # Застосування
    team_ids = fields.Many2many('crm.team', string='Команди продажів')
    channel = fields.Selection([
        ('direct', 'Прямі продажі'),
        ('retail', 'Роздрібна торгівля'),
        ('wholesale', 'Оптова торгівля'),
        ('online', 'Онлайн продажі'),
        ('partner', 'Через партнерів'),
        ('export', 'Експорт'),
        ('b2b', 'B2B продажі'),
        ('b2c', 'B2C продажі')
    ], 'Канал продажів')

    # Лінії шаблону
    line_ids = fields.One2many('sale.forecast.template.line', 'template_id', 'Позиції шаблону')

    # Методологічні примітки
    methodology_notes = fields.Text('Методологічні примітки')

    active = fields.Boolean('Активний', default=True)


class SaleForecastTemplateLine(models.Model):
    """Лінії шаблону прогнозу"""
    _name = 'sale.forecast.template.line'
    _description = 'Лінія шаблону прогнозу'

    template_id = fields.Many2one('sale.forecast.template', 'Шаблон', required=True, ondelete='cascade')

    product_id = fields.Many2one('product.product', 'Товар')
    product_category_id = fields.Many2one('product.category', 'Категорія товарів')

    description = fields.Char('Опис', required=True)

    # Значення за замовчуванням
    default_qty = fields.Float('Кількість за замовчуванням', default=1.0)
    default_price = fields.Float('Ціна за замовчуванням')
    default_probability = fields.Float('Ймовірність за замовчуванням, %', default=50.0)

    sequence = fields.Integer('Послідовність', default=10)