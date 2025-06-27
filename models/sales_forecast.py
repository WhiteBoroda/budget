# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import ValidationError


class SalesForecast(models.Model):
    """Прогноз продажів - розширення стандартної моделі Sales"""
    _name = 'sale.forecast'
    _description = 'Прогноз продажів'
    _order = 'period_id desc, team_id, product_category_id'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    def _compute_display_name(self):
        for record in self:
            team_name = record.team_id.name if record.team_id else 'Без команди'
            period_name = record.period_id.name if record.period_id else 'Без періоду'
            record.display_name = f"Прогноз {team_name} - {period_name}"

    display_name = fields.Char('Назва', compute='_compute_display_name', store=False)

    # Основні параметри
    period_id = fields.Many2one('budget.period', 'Період', required=True)
    team_id = fields.Many2one('crm.team', 'Команда продажів', required=True)
    user_id = fields.Many2one('res.users', 'Відповідальний', required=True, default=lambda self: self.env.user)

    # Географія та сегментація
    country_id = fields.Many2one('res.country', 'Країна')
    state_id = fields.Many2one('res.country.state', 'Область/Штат')

    # Канали продажів
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
    ], 'Канал продажів', required=True)

    # Сегментація клієнтів
    customer_segment = fields.Selection([
        ('new', 'Нові клієнти'),
        ('existing', 'Існуючі клієнти'),
        ('vip', 'VIP клієнти'),
        ('corporate', 'Корпоративні'),
        ('retail', 'Роздрібні'),
        ('government', 'Державні')
    ], 'Сегмент клієнтів')

    state = fields.Selection([
        ('draft', 'Чернетка'),
        ('review', 'На розгляді'),
        ('approved', 'Затверджений'),
        ('revision', 'Доопрацювання'),
        ('locked', 'Заблокований')
    ], 'Статус', default='draft', required=True, tracking=True)

    # Підсумкові показники
    total_forecast_amount = fields.Monetary('Загальний прогноз', compute='_compute_totals', store=True)
    total_forecast_qty = fields.Float('Загальна кількість', compute='_compute_totals', store=True)
    total_margin = fields.Monetary('Загальна маржа', compute='_compute_totals', store=True)
    margin_percent = fields.Float('Маржинальність, %', compute='_compute_totals', store=True)

    currency_id = fields.Many2one('res.currency', 'Валюта',
                                  default=lambda self: self.env.company.currency_id)
    company_id = fields.Many2one('res.company', 'Підприємство',
                                 default=lambda self: self.env.company)

    # Лінії прогнозу
    line_ids = fields.One2many('sale.forecast.line', 'forecast_id', 'Позиції прогнозу')

    # Аналітичні дані
    previous_period_sales = fields.Monetary('Продажі попереднього періоду', readonly=True)
    growth_rate = fields.Float('Темп росту, %', compute='_compute_growth_rate', store=True)

    # Базис для прогнозування
    forecast_base = fields.Selection([
        ('manual', 'Ручний ввід'),
        ('historical', 'Історичні дані'),
        ('pipeline', 'Pipeline продажів'),
        ('market', 'Ринкові дані'),
        ('combined', 'Комбінований')
    ], 'Базис прогнозування', default='manual')

    # Налаштування затвердження
    approved_by_id = fields.Many2one('res.users', 'Затверджено')
    approval_date = fields.Datetime('Дата затвердження')

    notes = fields.Text('Примітки')

    @api.depends('line_ids.forecast_amount', 'line_ids.forecast_qty', 'line_ids.margin_amount')
    def _compute_totals(self):
        for record in self:
            record.total_forecast_amount = sum(record.line_ids.mapped('forecast_amount'))
            record.total_forecast_qty = sum(record.line_ids.mapped('forecast_qty'))
            record.total_margin = sum(record.line_ids.mapped('margin_amount'))
            if record.total_forecast_amount:
                record.margin_percent = (record.total_margin / record.total_forecast_amount) * 100
            else:
                record.margin_percent = 0.0

    @api.depends('total_forecast_amount', 'previous_period_sales')
    def _compute_growth_rate(self):
        for record in self:
            if record.previous_period_sales:
                record.growth_rate = ((record.total_forecast_amount - record.previous_period_sales) /
                                      record.previous_period_sales) * 100
            else:
                record.growth_rate = 0.0

    def action_submit_for_review(self):
        """Подача на розгляд"""
        self.state = 'review'
        self.message_post(body="Прогноз подано на розгляд")

    def action_approve(self):
        """Затвердження прогнозу"""
        self.write({
            'state': 'approved',
            'approved_by_id': self.env.user.id,
            'approval_date': fields.Datetime.now()
        })
        self.message_post(body="Прогноз затверджено")

    def action_request_revision(self):
        """Відправка на доопрацювання"""
        self.state = 'revision'
        self.message_post(body="Прогноз відправлено на доопрацювання")

    def action_lock(self):
        """Блокування прогнозу"""
        self.state = 'locked'

    def copy_from_previous_period(self, growth_factor=1.0):
        """Копіювання з попереднього періоду"""
        # Логіка копіювання з попереднього періоду
        pass


class SalesForecastLine(models.Model):
    """Позиції прогнозу продажів"""
    _name = 'sale.forecast.line'
    _description = 'Позиції прогнозу продажів'

    forecast_id = fields.Many2one('sale.forecast', 'Прогноз', required=True, ondelete='cascade')

    # Товар та категорія
    product_id = fields.Many2one('product.product', 'Товар')
    product_category_id = fields.Many2one('product.category', 'Категорія товару')
    product_brand = fields.Char('Бренд')

    # Прогнозні показники
    forecast_qty = fields.Float('Прогнозна кількість', required=True)
    forecast_price = fields.Monetary('Прогнозна ціна', required=True)
    forecast_amount = fields.Monetary('Прогнозна сума', compute='_compute_forecast_amount', store=True)

    # Собівартість та маржа
    cost_price = fields.Monetary('Собівартість')
    margin_amount = fields.Monetary('Маржа', compute='_compute_margin', store=True)
    margin_percent = fields.Float('Маржа, %', compute='_compute_margin', store=True)

    # Знижки та умови
    discount_percent = fields.Float('Знижка, %', default=0.0)
    return_percent = fields.Float('Відсоток повернень, %', default=0.0)

    # Валюта
    currency_id = fields.Many2one('res.currency', related='forecast_id.currency_id', readonly=True)

    # Аналітика
    analytic_account_id = fields.Many2one('account.analytic.account', 'Аналітичний рахунок')

    # Додаткова інформація
    confidence_level = fields.Selection([
        ('low', 'Низький (50-70%)'),
        ('medium', 'Середній (70-85%)'),
        ('high', 'Високий (85-95%)'),
        ('certain', 'Впевнений (95%+)')
    ], 'Рівень впевненості', default='medium')

    notes = fields.Text('Примітки')

    @api.depends('forecast_qty', 'forecast_price', 'discount_percent')
    def _compute_forecast_amount(self):
        for line in self:
            amount = line.forecast_qty * line.forecast_price
            if line.discount_percent:
                amount *= (1 - line.discount_percent / 100)
            line.forecast_amount = amount

    @api.depends('forecast_amount', 'cost_price', 'forecast_qty')
    def _compute_margin(self):
        for line in self:
            total_cost = line.cost_price * line.forecast_qty
            line.margin_amount = line.forecast_amount - total_cost
            if line.forecast_amount:
                line.margin_percent = (line.margin_amount / line.forecast_amount) * 100
            else:
                line.margin_percent = 0.0


class SalesForecastTemplate(models.Model):
    """Шаблони прогнозів продажів"""
    _name = 'sale.forecast.template'
    _description = 'Шаблони прогнозів продажів'

    name = fields.Char('Назва шаблону', required=True)
    description = fields.Text('Опис')

    team_id = fields.Many2one('crm.team', 'Команда продажів')
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
    ], 'Канал продажів')

    # Шаблонні лінії
    line_ids = fields.One2many('sale.forecast.template.line', 'template_id', 'Позиції шаблону')

    active = fields.Boolean('Активний', default=True)

    def create_forecast_from_template(self, period_id, team_id=None):
        """Створення прогнозу з шаблону"""
        forecast_vals = {
            'period_id': period_id,
            'team_id': team_id or self.team_id.id,
            'channel': self.channel,
            'forecast_base': 'manual',
            'user_id': self.env.user.id,
        }

        forecast = self.env['sale.forecast'].create(forecast_vals)

        # Копіюємо лінії
        for template_line in self.line_ids:
            line_vals = {
                'forecast_id': forecast.id,
                'product_id': template_line.product_id.id,
                'product_category_id': template_line.product_category_id.id,
                'forecast_qty': template_line.default_qty,
                'forecast_price': template_line.default_price,
                'cost_price': template_line.cost_price,
                'confidence_level': template_line.confidence_level,
            }
            self.env['sale.forecast.line'].create(line_vals)

        return forecast


class SalesForecastTemplateLine(models.Model):
    """Позиції шаблону прогнозу"""
    _name = 'sale.forecast.template.line'
    _description = 'Позиції шаблону прогнозу'

    template_id = fields.Many2one('sale.forecast.template', 'Шаблон', required=True, ondelete='cascade')
    product_id = fields.Many2one('product.product', 'Товар')
    product_category_id = fields.Many2one('product.category', 'Категорія товару')

    default_qty = fields.Float('Кількість за замовчуванням')
    default_price = fields.Monetary('Ціна за замовчуванням')
    cost_price = fields.Monetary('Собівартість')

    confidence_level = fields.Selection([
        ('low', 'Низький'),
        ('medium', 'Середній'),
        ('high', 'Високий'),
        ('certain', 'Впевнений')
    ], 'Рівень впевненості', default='medium')

    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)