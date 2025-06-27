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
            if record.forecast_scope == 'team' and record.team_id:
                scope_name = record.team_id.name
            elif record.forecast_scope == 'cbo' and record.cbo_id:
                scope_name = record.cbo_id.name
            elif record.forecast_scope == 'project' and record.project_id:
                scope_name = record.project_id.name
            elif record.forecast_scope == 'combined':
                parts = []
                if record.team_id:
                    parts.append(record.team_id.name)
                if record.cbo_id:
                    parts.append(record.cbo_id.name)
                if record.project_id:
                    parts.append(record.project_id.name)
                scope_name = ' + '.join(parts) if parts else 'Комбінований'
            else:
                scope_name = 'Без області'

            period_name = record.period_id.name if record.period_id else 'Без періоду'
            record.display_name = f"Прогноз {scope_name} - {period_name}"

    display_name = fields.Char('Назва', compute='_compute_display_name', store=False)

    # Основні параметри - гнучка структура відповідальності
    period_id = fields.Many2one('budget.period', 'Період', required=True,
                                domain="[('company_id', '=', company_id)]")

    # Можна планувати на різні рівні
    forecast_scope = fields.Selection([
        ('team', 'Команда продажів'),
        ('cbo', 'ЦБО (кластер/бренд/напрямок)'),
        ('project', 'Проект'),
        ('combined', 'Комбінований')
    ], 'Область прогнозування', required=True, default='team')

    team_id = fields.Many2one('crm.team', 'Команда продажів')
    cbo_id = fields.Many2one('budget.responsibility.center', 'ЦБО')
    project_id = fields.Many2one('project.project', 'Проект')

    user_id = fields.Many2one('res.users', 'Відповідальний', required=True, default=lambda self: self.env.user)

    # Географія та сегментація
    country_id = fields.Many2one('res.country', 'Країна')
    state_id = fields.Many2one('res.country.state', 'Область/Штат',
                               domain="[('country_id', '=', country_id)]")

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
                                 default=lambda self: self.env.company, required=True)

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
        # Для combined залишаємо всі поля доступними

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

    @api.onchange('company_id')
    def _onchange_company_id(self):
        """Очистка полів при зміні компанії"""
        if self.company_id:
            # Очищаємо команду якщо вона не належить новій компанії
            if self.team_id and self.team_id.company_id != self.company_id:
                self.team_id = False
            # Очищаємо ЦБО якщо воно не належить новій компанії
            if self.cbo_id and self.company_id not in self.cbo_id.company_ids:
                self.cbo_id = False
            # Очищаємо проект якщо він не належить новій компанії
            if self.project_id and self.project_id.company_id != self.company_id:
                self.project_id = False
            # Очищаємо період якщо він не належить новій компанії
            if self.period_id and self.period_id.company_id != self.company_id:
                self.period_id = False
            # Встановлюємо валюту компанії
            self.currency_id = self.company_id.currency_id

    @api.onchange('country_id')
    def _onchange_country_id(self):
        """Очистка області при зміні країни"""
        if self.country_id and self.state_id:
            if self.state_id.country_id != self.country_id:
                self.state_id = False

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
        # Шукаємо попередній період
        previous_period = self.env['budget.period'].search([
            ('company_id', '=', self.company_id.id),
            ('date_end', '<', self.period_id.date_start),
            ('period_type', '=', self.period_id.period_type)
        ], order='date_end desc', limit=1)

        if not previous_period:
            return False

        # Шукаємо прогноз попереднього періоду для цієї команди
        previous_forecast = self.env['sale.forecast'].search([
            ('period_id', '=', previous_period.id),
            ('team_id', '=', self.team_id.id),
            ('company_id', '=', self.company_id.id),
            ('state', '=', 'approved')
        ], limit=1)

        if previous_forecast:
            self.previous_period_sales = previous_forecast.total_forecast_amount

            # Копіюємо лінії з ростом
            for prev_line in previous_forecast.line_ids:
                self.env['sale.forecast.line'].create({
                    'forecast_id': self.id,
                    'product_id': prev_line.product_id.id,
                    'product_category_id': prev_line.product_category_id.id,
                    'product_brand': prev_line.product_brand,
                    'forecast_qty': prev_line.forecast_qty * growth_factor,
                    'forecast_price': prev_line.forecast_price * growth_factor,
                    'cost_price': prev_line.cost_price,
                    'discount_percent': prev_line.discount_percent,
                    'return_percent': prev_line.return_percent,
                    'confidence_level': prev_line.confidence_level,
                    'notes': f'Скопійовано з {previous_period.name} з ростом {(growth_factor - 1) * 100:.1f}%'
                })

        return True


class SalesForecastLine(models.Model):
    """Позиції прогнозу продажів"""
    _name = 'sale.forecast.line'
    _description = 'Позиції прогнозу продажів'

    forecast_id = fields.Many2one('sale.forecast', 'Прогноз', required=True, ondelete='cascade')

    # Товар та категорія з доменами
    product_id = fields.Many2one('product.product', 'Товар',
                                 domain="[('sale_ok', '=', True), '|', ('company_id', '=', False), ('company_id', '=', company_id)]")
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

    # Валюта та компанія
    currency_id = fields.Many2one('res.currency', related='forecast_id.currency_id', readonly=True)
    company_id = fields.Many2one('res.company', related='forecast_id.company_id', readonly=True, store=True)

    # Аналітика
    analytic_account_id = fields.Many2one('account.analytic.account', 'Аналітичний рахунок',
                                          domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]")

    # Додаткова інформація
    confidence_level = fields.Selection([
        ('low', 'Низький (50-70%)'),
        ('medium', 'Середній (70-85%)'),
        ('high', 'Високий (85-95%)'),
        ('certain', 'Впевнений (95%+)')
    ], 'Рівень впевненості', default='medium')

    notes = fields.Text('Примітки')

    @api.onchange('product_id')
    def _onchange_product_id(self):
        """Заповнення даних товару"""
        if self.product_id:
            self.product_category_id = self.product_id.categ_id
            self.forecast_price = self.product_id.list_price
            self.cost_price = self.product_id.standard_price
            if hasattr(self.product_id, 'brand'):
                self.product_brand = self.product_id.brand

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
    company_id = fields.Many2one('res.company', 'Підприємство', default=lambda self: self.env.company)
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
            'company_id': self.company_id.id,
            'channel': self.channel,
            'forecast_base': 'manual',
            'user_id': self.env.user.id,
            'forecast_scope': 'team'  # За замовчуванням команда
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
    company_id = fields.Many2one('res.company', related='template_id.company_id', readonly=True, store=True)

    product_id = fields.Many2one('product.product', 'Товар',
                                 domain="[('sale_ok', '=', True), '|', ('company_id', '=', False), ('company_id', '=', company_id)]")
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

    currency_id = fields.Many2one('res.currency', related='template_id.company_id.currency_id', readonly=True)

    @api.onchange('product_id')
    def _onchange_product_id(self):
        """Заповнення даних товару"""
        if self.product_id:
            self.product_category_id = self.product_id.categ_id
            self.default_price = self.product_id.list_price
            self.cost_price = self.product_id.standard_price


class SalesPlanWizard(models.TransientModel):
    """Майстер створення плану продажів"""
    _name = 'sales.plan.wizard'
    _description = 'Майстер створення плану продажів'

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

    team_id = fields.Many2one('crm.team', 'Команда продажів',
                              domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]")
    cbo_id = fields.Many2one('budget.responsibility.center', 'ЦБО',
                             domain="[('company_ids', 'in', [company_id])]")
    project_id = fields.Many2one('project.project', 'Проект',
                                 domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]")

    product_category_ids = fields.Many2many('product.category', string='Категорії товарів')

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
            ('forecast_scope', '=', self.forecast_scope)
        ]

        # Додаємо специфічні умови в залежності від області
        if self.forecast_scope == 'team':
            domain.append(('team_id', '=', self.team_id.id))
        elif self.forecast_scope == 'cbo':
            domain.append(('cbo_id', '=', self.cbo_id.id))
        elif self.forecast_scope == 'project':
            domain.append(('project_id', '=', self.project_id.id))

        existing_forecast = self.env['sale.forecast'].search(domain)
        if existing_forecast:
            raise ValidationError('Прогноз для цього періоду та області вже існує!')

        # Створюємо новий прогноз
        forecast_vals = {
            'period_id': self.period_id.id,
            'company_id': self.company_id.id,
            'forecast_scope': self.forecast_scope,
            'team_id': self.team_id.id if self.team_id else False,
            'cbo_id': self.cbo_id.id if self.cbo_id else False,
            'project_id': self.project_id.id if self.project_id else False,
            'state': 'draft',
            'responsible_user_id': self.env.user.id,
            'channel': 'direct',  # По умолчанию
            'forecast_base': 'manual'
        }

        new_forecast = self.env['sale.forecast'].create(forecast_vals)

        # Якщо потрібно копіювати з попереднього періоду
        if self.copy_previous and self.base_period_id:
            success = new_forecast.copy_from_previous_period(1 + self.growth_rate / 100)
            if not success:
                # Якщо не знайдено попередній прогноз, створюємо базові лінії
                self._create_default_lines(new_forecast)

        return {
            'type': 'ir.actions.act_window',
            'name': 'Прогноз продажів',
            'res_model': 'sale.forecast',
            'res_id': new_forecast.id,
            'view_mode': 'form',
            'target': 'current'
        }

    def _create_default_lines(self, forecast):
        """Створення базових ліній якщо не копіюємо з попереднього періоду"""
        if not self.product_category_ids:
            return

        for category in self.product_category_ids:
            # Створюємо базову лінію для категорії
            self.env['sale.forecast.line'].create({
                'forecast_id': forecast.id,
                'product_category_id': category.id,
                'forecast_qty': 1.0,
                'forecast_price': 100.0,
                'confidence_level': 'medium',
                'notes': f'Базова лінія для категорії {category.name}'
            })

    """Шаблони прогнозів продажів"""
    _name = 'sale.forecast.template'
    _description = 'Шаблони прогнозів продажів'

    name = fields.Char('Назва шаблону', required=True)
    description = fields.Text('Опис')

    team_id = fields.Many2one('crm.team', 'Команда продажів')
    company_id = fields.Many2one('res.company', 'Підприємство', default=lambda self: self.env.company)
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
            'company_id': self.company_id.id,
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
    company_id = fields.Many2one('res.company', related='template_id.company_id', readonly=True, store=True)

    product_id = fields.Many2one('product.product', 'Товар',
                                 domain="[('sale_ok', '=', True), '|', ('company_id', '=', False), ('company_id', '=', company_id)]")
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

    currency_id = fields.Many2one('res.currency', related='template_id.company_id.currency_id', readonly=True)

    @api.onchange('product_id')
    def _onchange_product_id(self):
        """Заповнення даних товару"""
        if self.product_id:
            self.product_category_id = self.product_id.categ_id
            self.default_price = self.product_id.list_price
            self.cost_price = self.product_id.standard_price