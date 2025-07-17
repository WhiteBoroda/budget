# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
import json


class BudgetPlan(models.Model):
    """Бюджетний план з інтеграцією продажів - ВИПРАВЛЕНО ДЛЯ ODOO 17"""
    _name = 'budget.plan'
    _description = 'Бюджетний план'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'period_id desc, cbo_id, budget_type_id'
    _rec_name = 'display_name'

    # ОСНОВНІ ПОЛЯ
    name = fields.Char(
        'Назва бюджету',
        required=True,
        tracking=True,
        help="Назва бюджетного плану"
    )

    display_name = fields.Char(
        'Повна назва',
        compute='_compute_display_name',
        store=True,
        help="Автоматично сформована повна назва"
    )

    code = fields.Char(
        'Код бюджету',
        tracking=True,
        help="Унікальний код бюджету"
    )

    description = fields.Text(
        'Опис',
        help="Детальний опис бюджету"
    )

    # ЗВ'ЯЗКИ З ІНШИМИ МОДЕЛЯМИ
    budget_type_id = fields.Many2one(
        'budget.type',
        'Тип бюджету',
        required=True,
        tracking=True,
        ondelete='restrict'
    )

    cbo_id = fields.Many2one(
        'budget.responsibility.center',
        'ЦБО',
        required=True,
        tracking=True,
        ondelete='restrict',
        help="Центр бюджетної відповідальності"
    )

    period_id = fields.Many2one(
        'budget.period',
        'Бюджетний період',
        required=True,
        tracking=True,
        ondelete='restrict'
    )

    company_ids = fields.Many2many(
        'res.company',
        string='Компанії',
        default=lambda self: [(6, 0, [self.env.company.id])],
        required=True
    )

    currency_id = fields.Many2one(
        'res.currency',
        'Валюта',
        compute='_compute_currency_id',
        store=True
    )

    # ІНТЕГРАЦІЯ З ПРОДАЖАМИ
    sales_forecast_ids = fields.Many2many(
        'sale.forecast',
        string='Прогнози продажів',
        domain="[('period_id', '=', period_id), ('state', '=', 'approved')]",
        help="Пов'язані прогнози продажів для цього бюджету"
    )

    # КОНСОЛІДАЦІЯ ТА ІЄРАРХІЯ
    parent_budget_id = fields.Many2one(
        'budget.plan',
        'Батьківський бюджет',
        help="Консолідований бюджет вищого рівня"
    )

    child_budget_ids = fields.One2many(
        'budget.plan',
        'parent_budget_id',
        'Дочірні бюджети',
        help="Бюджети дочірніх ЦБО"
    )

    # АВТОМАТИЧНА КОНСОЛІДАЦІЯ
    auto_consolidation = fields.Boolean(
        related='cbo_id.auto_consolidation',
        readonly=True,
        help="Чи увімкнена автоматична консолідація для цього ЦБО"
    )

    consolidation_method = fields.Selection(
        related='cbo_id.consolidation_method',
        readonly=True,
        help="Метод консолідації бюджету"
    )

    # ВЕРСІЙНІСТЬ
    version = fields.Char(
        'Версія',
        default='1.0',
        help="Версія бюджету для контролю змін"
    )

    is_baseline = fields.Boolean(
        'Базова версія',
        help="Затверджена базова версія бюджету"
    )

    baseline_budget_id = fields.Many2one(
        'budget.plan',
        'Базовий бюджет',
        help="Посилання на базову версію бюджету"
    )

    # ПОЛЕ ДЛЯ ФІЛЬТРАЦІЇ ЦБО (computed)
    cbo_domain = fields.Text(
        'Домен ЦБО',
        compute='_compute_cbo_domain',
        help="JSON домен для фільтрації доступних ЦБО"
    )

    # СТАТУС БЮДЖЕТУ - ВИПРАВЛЕНО для Odoo 17 (без states)
    state = fields.Selection([
        ('draft', 'Чернетка'),
        ('planning', 'Планування'),
        ('coordination', 'Узгодження'),
        ('approved', 'Затверджений'),
        ('revision', 'Доопрацювання'),
        ('executed', 'Виконується'),
        ('closed', 'Закритий')
    ], 'Статус', default='draft', required=True, tracking=True, index=True)

    # ФІНАНСОВІ ПОЛЯ - ВИПРАВЛЕНО для Odoo 17 (без states)
    planned_amount = fields.Monetary(
        'Планова сума',
        compute='_compute_totals',
        store=True,
        currency_field='currency_id',
        help="Загальна планова сума бюджету"
    )

    actual_amount = fields.Monetary(
        'Фактична сума',
        compute='_compute_actual_amount',
        store=True,
        currency_field='currency_id',
        help="Фактично витрачена сума"
    )

    committed_amount = fields.Monetary(
        'Зарезервована сума',
        compute='_compute_committed_amount',
        store=True,
        currency_field='currency_id',
        help="Зарезервована для витрат сума"
    )

    available_amount = fields.Monetary(
        'Доступна сума',
        compute='_compute_available_amount',
        store=True,
        currency_field='currency_id',
        help="Доступна для витрат сума"
    )

    # ПОЛЯ ДЛЯ АНАЛІЗУ ВІДХИЛЕНЬ
    variance_amount = fields.Monetary(
        'Відхилення',
        compute='_compute_variance',
        store=True,
        currency_field='currency_id',
        help="Відхилення факту від плану"
    )

    variance_percent = fields.Float(
        'Відхилення, %',
        compute='_compute_variance',
        store=True,
        help="Відхилення у відсотках"
    )

    execution_percent = fields.Float(
        'Виконання, %',
        compute='_compute_execution',
        store=True,
        help="Відсоток виконання бюджету"
    )

    # ВІДПОВІДАЛЬНІ ОСОБИ
    responsible_user_id = fields.Many2one(
        'res.users',
        'Відповідальний планувальник',
        required=True,
        default=lambda self: self.env.user,
        index=True,
        tracking=True
    )

    coordinator_user_id = fields.Many2one(
        'res.users',
        'Координатор',
        tracking=True
    )

    approver_user_id = fields.Many2one(
        'res.users',
        'Затверджувач',
        tracking=True
    )

    approved_by_id = fields.Many2one(
        'res.users',
        'Затверджено',
        readonly=True
    )

    # ДАТИ
    date_created = fields.Datetime(
        'Дата створення',
        default=fields.Datetime.now,
        readonly=True
    )

    date_approved = fields.Datetime(
        'Дата затвердження',
        readonly=True
    )

    date_closed = fields.Datetime(
        'Дата закриття',
        readonly=True
    )

    submission_deadline = fields.Date(
        'Крайній термін подання',
        required=True,
        default=fields.Date.today,
        help="Останній день для подання бюджету на затвердження"
    )

    # НАЛАШТУВАННЯ РОЗРАХУНКІВ
    calculation_method = fields.Selection(
        related='budget_type_id.calculation_method',
        readonly=True,
        help="Метод розрахунку бюджету"
    )

    # ВАЛЮТНІ НАЛАШТУВАННЯ
    budget_currency_setting_id = fields.Many2one(
        'budget.currency.setting',
        'Валютні налаштування',
        help="Налаштування для роботи з валютами"
    )

    # ДОДАТКОВІ ПОЛЯ
    priority = fields.Selection([
        ('low', 'Низький'),
        ('normal', 'Нормальний'),
        ('high', 'Високий'),
        ('urgent', 'Терміновий')
    ], 'Пріоритет', default='normal')

    active = fields.Boolean(
        'Активний',
        default=True,
        help="Зніміть галочку для архівування бюджету"
    )

    notes = fields.Text(
        'Примітки та обґрунтування',
        help="Додаткові коментарі та обґрунтування бюджету"
    )

    # ЗВ'ЯЗКИ З РЯДКАМИ БЮДЖЕТУ
    line_ids = fields.One2many(
        'budget.plan.line',
        'plan_id',
        'Рядки бюджету'
    )

    # COMPUTED ПОЛЯ ДЛЯ ODOO 17 (замість states)
    @api.depends('state')
    def _compute_is_readonly(self):
        """Визначає чи можна редагувати бюджет"""
        for plan in self:
            plan.is_readonly = plan.state in ['approved', 'executed', 'closed']

    is_readonly = fields.Boolean(
        'Тільки для читання',
        compute='_compute_is_readonly',
        help="Визначає доступність для редагування"
    )

    @api.depends('state')
    def _compute_can_edit_lines(self):
        """Визначає чи можна редагувати рядки бюджету"""
        for plan in self:
            plan.can_edit_lines = plan.state in ['draft', 'planning', 'revision']

    can_edit_lines = fields.Boolean(
        'Можна редагувати рядки',
        compute='_compute_can_edit_lines'
    )

    # ОСНОВНІ COMPUTED МЕТОДИ
    @api.depends('name', 'cbo_id.name', 'budget_type_id.name', 'period_id.name')
    def _compute_display_name(self):
        """Формування повної назви бюджету"""
        for record in self:
            parts = []
            if record.cbo_id:
                parts.append(record.cbo_id.name)
            if record.budget_type_id:
                parts.append(record.budget_type_id.name)
            if record.period_id:
                parts.append(record.period_id.name)
            if record.name:
                parts.append(record.name)

            record.display_name = ' / '.join(parts) if parts else _('Новий бюджет')

    @api.depends('company_ids')
    def _compute_currency_id(self):
        """Обчислення валюти з першої компанії"""
        for record in self:
            if record.company_ids:
                record.currency_id = record.company_ids[0].currency_id
            else:
                record.currency_id = self.env.company.currency_id

    @api.depends('budget_type_id', 'company_id')
    def _compute_cbo_domain(self):
        """Обчислення домену для ЦБО на основі типу бюджету та компанії"""
        for record in self:
            domain = []

            # Базовий фільтр - активні ЦБО
            domain.append(('active', '=', True))

            # Фільтр по компанії
            if record.company_id:
                domain.append(('company_id', '=', record.company_id.id))

            # ВИПРАВЛЕНО: Замість allowed_cbo_types використовуємо existing поля
            if record.budget_type_id:
                # Якщо в типі бюджету є обмеження по рівню
                if hasattr(record.budget_type_id,
                           'budget_level_restriction') and record.budget_type_id.budget_level_restriction:
                    domain.append(('budget_level', '=', record.budget_type_id.budget_level_restriction))

                # Якщо в типі бюджету є обмеження по категорії ЦБО
                if hasattr(record.budget_type_id, 'cbo_category_ids') and record.budget_type_id.cbo_category_ids:
                    domain.append(('category_id', 'in', record.budget_type_id.cbo_category_ids.ids))

            # Перетворюємо домен у JSON строку для використання в представленнях
            record.cbo_domain = json.dumps(domain)

    @api.depends('line_ids.planned_amount')
    def _compute_totals(self):
        """Обчислення загальних сум"""
        for budget in self:
            budget.planned_amount = sum(budget.line_ids.mapped('planned_amount'))

    @api.depends('line_ids.actual_amount')
    def _compute_actual_amount(self):
        """Обчислення фактичних витрат"""
        for budget in self:
            # Отримуємо фактичні витрати з execution records
            executions = self.env['budget.execution'].search([('budget_plan_id', '=', budget.id)])
            budget.actual_amount = sum(executions.mapped('actual_amount'))

    @api.depends('line_ids.committed_amount')
    def _compute_committed_amount(self):
        """Обчислення зарезервованих сум"""
        for budget in self:
            budget.committed_amount = sum(budget.line_ids.mapped('committed_amount'))

    @api.depends('planned_amount', 'actual_amount', 'committed_amount')
    def _compute_available_amount(self):
        """Обчислення доступної суми"""
        for budget in self:
            budget.available_amount = budget.planned_amount - budget.actual_amount - budget.committed_amount

    @api.depends('planned_amount', 'actual_amount')
    def _compute_variance(self):
        """Обчислення відхилень"""
        for budget in self:
            budget.variance_amount = budget.actual_amount - budget.planned_amount

            if budget.planned_amount:
                budget.variance_percent = (budget.variance_amount / budget.planned_amount) * 100
            else:
                budget.variance_percent = 0.0

    @api.depends('planned_amount', 'actual_amount')
    def _compute_execution(self):
        """Обчислення відсотка виконання"""
        for budget in self:
            if budget.planned_amount:
                budget.execution_percent = (budget.actual_amount / budget.planned_amount) * 100
            else:
                budget.execution_percent = 0.0

    # МЕТОДИ WORKFLOW
    def action_start_planning(self):
        """Почати планування"""
        self.ensure_one()
        self.state = 'planning'
        self.message_post(body=_("Бюджет переведено в стан планування"))

    def action_submit_for_coordination(self):
        """Подати на узгодження"""
        self.ensure_one()
        if not self.line_ids:
            raise UserError(_("Неможливо подати порожній бюджет на узгодження"))

        self.state = 'coordination'
        self.message_post(body=_("Бюджет подано на узгодження"))

        # Автоматична консолідація (якщо налаштована)
        if self.auto_consolidation and self.cbo_id.parent_id:
            self._create_consolidation_budget()

    def action_approve(self):
        """Затвердити бюджет"""
        self.ensure_one()
        self.write({
            'state': 'approved',
            'approved_by_id': self.env.user.id,
            'date_approved': fields.Datetime.now(),
            'is_baseline': True
        })
        self.message_post(body=_("Бюджет затверджено"))

        # Створення базових категорій (якщо потрібно)
        if not self.line_ids:
            self._create_default_budget_lines()

    def action_reject(self):
        """Відхилити бюджет"""
        self.ensure_one()
        self.state = 'revision'
        self.message_post(body=_("Бюджет відхилено для доопрацювання"))

    def action_close(self):
        """Закрити бюджет"""
        self.ensure_one()
        self.write({
            'state': 'closed',
            'date_closed': fields.Datetime.now()
        })
        self.message_post(body=_("Бюджет закрито"))

    def action_reopen(self):
        """Перевідкрити бюджет"""
        self.ensure_one()
        self.state = 'approved'
        self.date_closed = False
        self.message_post(body=_("Бюджет перевідкрито"))

    # МЕТОДИ КОНСОЛІДАЦІЇ
    def _create_consolidation_budget(self):
        """Створення консолідованого бюджету для батьківського ЦБО"""
        parent_cbo = self.cbo_id.parent_id
        if not parent_cbo:
            return

        # Пошук існуючого консолідованого бюджету
        consolidated_budget = self.search([
            ('period_id', '=', self.period_id.id),
            ('budget_type_id', '=', self.budget_type_id.id),
            ('cbo_id', '=', parent_cbo.id)
        ], limit=1)

        if not consolidated_budget:
            # Створення консолідованого бюджету
            consolidated_vals = {
                'name': f"Консолідований {self.budget_type_id.name} - {parent_cbo.name} - {self.period_id.name}",
                'period_id': self.period_id.id,
                'budget_type_id': self.budget_type_id.id,
                'cbo_id': parent_cbo.id,
                'company_id': self.company_id.id,
                'state': 'draft',
                'calculation_method': 'consolidation'
            }
            consolidated_budget = self.create(consolidated_vals)

        # Прив'язка до консолідованого бюджету
        self.parent_budget_id = consolidated_budget.id

        return consolidated_budget

    def _create_default_budget_lines(self):
        """Створення стандартних рядків бюджету на основі типу"""
        if self.budget_type_id and hasattr(self.budget_type_id, 'default_categories'):
            for category in self.budget_type_id.default_categories:
                self.env['budget.plan.line'].create({
                    'plan_id': self.id,
                    'budget_category_id': category.id,
                    'description': category.name,
                    'planned_amount': 0.0
                })

    # МЕТОДИ ІНТЕГРАЦІЇ З ПРОДАЖАМИ
    def action_sync_with_sales_forecast(self):
        """Синхронізація з прогнозами продажів"""
        self.ensure_one()

        if not self.sales_forecast_ids:
            raise UserError(_("Не обрано жодного прогнозу продажів для синхронізації"))

        for forecast in self.sales_forecast_ids:
            for forecast_line in forecast.line_ids:
                # Створення або оновлення рядків бюджету на основі прогнозу
                existing_line = self.line_ids.filtered(
                    lambda l: l.sales_forecast_line_id == forecast_line
                )

                if existing_line:
                    existing_line.planned_amount = forecast_line.forecast_amount
                else:
                    self.env['budget.plan.line'].create({
                        'plan_id': self.id,
                        'description': f"Прогноз: {forecast_line.product_id.name or forecast_line.product_category_id.name}",
                        'planned_amount': forecast_line.forecast_amount,
                        'sales_forecast_line_id': forecast_line.id,
                        'calculation_method': 'sales_forecast'
                    })

        self.message_post(body=_("Бюджет синхронізовано з прогнозами продажів"))

    # ДОДАТКОВІ МЕТОДИ
    def copy(self, default=None):
        """Копіювання бюджету"""
        default = default or {}
        default.update({
            'name': _('%s (копія)') % self.name,
            'state': 'draft',
            'date_approved': False,
            'date_closed': False,
            'approved_by_id': False,
            'is_baseline': False,
            'version': '1.0'
        })
        return super().copy(default)

    @api.model
    def create(self, vals):
        """Створення бюджету з автоматичною генерацією коду"""
        if not vals.get('code'):
            vals['code'] = self.env['ir.sequence'].next_by_code('budget.plan') or 'БП/'

        # Встановлення company_ids за замовчуванням
        if not vals.get('company_ids'):
            vals['company_ids'] = [(6, 0, [self.env.company.id])]

        budget = super().create(vals)

        # Повідомлення про створення
        budget.message_post_with_view(
            'mail.message_origin_link',
            body=f"Створено бюджет {budget.budget_type_id.name} для {budget.cbo_id.name}",
            message_type='notification'
        )

        return budget

    def name_get(self):
        """Кастомне відображення назви"""
        result = []
        for record in self:
            name = record.display_name or record.name
            result.append((record.id, name))
        return result

    @api.constrains('period_id', 'cbo_id', 'budget_type_id')
    def _check_unique_budget(self):
        """Перевірка унікальності бюджету"""
        for record in self:
            domain = [
                ('period_id', '=', record.period_id.id),
                ('cbo_id', '=', record.cbo_id.id),
                ('budget_type_id', '=', record.budget_type_id.id),
                ('id', '!=', record.id)
            ]

            if self.search_count(domain) > 0:
                raise ValidationError(_(
                    'Бюджет для ЦБО "%s", типу "%s" та періоду "%s" вже існує!'
                ) % (record.cbo_id.name, record.budget_type_id.name, record.period_id.name))


class BudgetPlanLine(models.Model):
    """Рядок бюджетного плану з інтеграцією продажів"""
    _name = 'budget.plan.line'
    _description = 'Рядок бюджетного плану'
    _order = 'sequence, id'

    # ЗВ'ЯЗОК З ПЛАНОМ
    plan_id = fields.Many2one(
        'budget.plan',
        'Бюджетний план',
        required=True,
        ondelete='cascade'
    )

    # ОСНОВНІ ПОЛЯ
    sequence = fields.Integer('Послідовність', default=10)

    description = fields.Char(
        'Назва статті',
        required=True,
        help="Назва бюджетної статті"
    )

    notes = fields.Text(
        'Примітки',
        help="Детальний опис статті витрат"
    )

    # ФІНАНСОВІ ПОЛЯ
    planned_amount = fields.Monetary(
        'Планова сума',
        required=True,
        currency_field='currency_id',
        help="Планова сума по статті"
    )

    actual_amount = fields.Monetary(
        'Фактична сума',
        compute='_compute_actual_amount',
        store=True,
        currency_field='currency_id',
        help="Фактично витрачена сума"
    )

    committed_amount = fields.Monetary(
        'Зарезервовано',
        default=0.0,
        currency_field='currency_id',
        help="Зарезервована сума"
    )

    # РОЗРАХУНКОВІ ПОЛЯ
    calculation_method = fields.Selection([
        ('manual', 'Ручний ввід'),
        ('norm_based', 'За нормативами'),
        ('percentage', 'Відсоток від доходів'),
        ('previous_period', 'На основі попереднього періоду'),
        ('sales_forecast', 'На основі прогнозу продажів'),
        ('consolidation', 'Консолідація')
    ], 'Метод розрахунку', default='manual')

    calculation_basis = fields.Text(
        'Основа розрахунку',
        help="Пояснення як розраховувалась сума"
    )

    # Деталізація для розрахунків
    quantity = fields.Float('Кількість')
    unit_price = fields.Monetary('Ціна за одиницю', currency_field='currency_id')
    percentage_base = fields.Float('Відсоток від бази')

    # ІНТЕГРАЦІЯ З ПРОДАЖАМИ
    sales_forecast_line_id = fields.Many2one(
        'sale.forecast.line',
        'Лінія прогнозу продажів',
        help="Пов'язана лінія прогнозу продажів"
    )

    # ЗВ'ЯЗАНІ ПОЛЯ
    currency_id = fields.Many2one(
        related='plan_id.company_id.currency_id',
        readonly=True
    )

    # АНАЛІТИЧНІ ПОЛЯ
    account_id = fields.Many2one(
        'account.account',
        'Рахунок обліку',
        help="Рахунок обліку для цієї статті"
    )

    analytic_account_id = fields.Many2one(
        'account.analytic.account',
        'Аналітичний рахунок',
        help="Аналітичний рахунок для деталізації"
    )

    # ПОЛЯ ДЛЯ КАТЕГОРІЙ ВИТРАТ
    budget_category_id = fields.Many2one(
        'budget.category',
        'Категорія витрат',
        help="Категорія бюджетних витрат"
    )

    # АНАЛІТИЧНІ ВИМІРИ
    department_id = fields.Many2one('hr.department', 'Підрозділ')
    project_id = fields.Many2one('project.project', 'Проект')

    # СЛУЖБОВІ ПОЛЯ
    is_consolidation = fields.Boolean('Консолідаційна лінія', default=False)

    # COMPUTED ПОЛЯ ДЛЯ ODOO 17 (замість states)
    @api.depends('plan_id.state')
    def _compute_is_editable(self):
        """Визначає чи можна редагувати рядок"""
        for line in self:
            line.is_editable = line.plan_id.state in ['draft', 'planning', 'revision']

    is_editable = fields.Boolean('Можна редагувати', compute='_compute_is_editable')

    @api.depends('plan_id')
    def _compute_actual_amount(self):
        """Розрахунок фактичної суми з execution records"""
        for line in self:
            executions = self.env['budget.execution'].search([
                ('budget_plan_id', '=', line.plan_id.id),
                ('budget_line_id', '=', line.id)
            ])
            line.actual_amount = sum(executions.mapped('actual_amount'))

    # ONCHANGE МЕТОДИ
    @api.onchange('quantity', 'unit_price')
    def _onchange_quantity_price(self):
        """Автоматичний розрахунок суми"""
        if self.calculation_method == 'manual' and self.quantity and self.unit_price:
            self.planned_amount = self.quantity * self.unit_price

    @api.onchange('sales_forecast_line_id')
    def _onchange_sales_forecast_line(self):
        """Підтягування даних з прогнозу продажів"""
        if self.sales_forecast_line_id:
            forecast_line = self.sales_forecast_line_id
            self.planned_amount = forecast_line.forecast_amount
            self.description = f"На основі прогнозу: {forecast_line.product_id.name or forecast_line.product_category_id.name}"
            self.calculation_basis = f"Прогноз: {forecast_line.forecast_qty} x {forecast_line.forecast_price}"
            self.calculation_method = 'sales_forecast'

    @api.onchange('budget_category_id')
    def _onchange_budget_category(self):
        """Автоматичне заповнення рахунку з категорії"""
        if self.budget_category_id:
            if not self.description:
                self.description = self.budget_category_id.name
            if self.budget_category_id.default_account_id and not self.account_id:
                self.account_id = self.budget_category_id.default_account_id

    # CRUD МЕТОДИ
    @api.model
    def create(self, vals_list):
        """Створення ліній бюджету з підтримкою batch операцій"""
        if isinstance(vals_list, dict):
            vals_list = [vals_list]

        # Обробка кожного запису
        for vals in vals_list:
            # Валідація обов'язкових полів
            if not vals.get('plan_id'):
                raise ValidationError('Не вказано план бюджету для лінії')

            if not vals.get('description'):
                if vals.get('budget_category_id'):
                    category = self.env['budget.category'].browse(vals['budget_category_id'])
                    vals['description'] = category.name if category.exists() else 'Нова позиція'
                else:
                    vals['description'] = 'Нова позиція бюджету'

            # Встановлення значень за замовчуванням
            if not vals.get('planned_amount'):
                vals['planned_amount'] = 0.0

            if not vals.get('calculation_method'):
                vals['calculation_method'] = 'manual'

            # Автоматичне призначення рахунку з категорії
            if vals.get('budget_category_id') and not vals.get('account_id'):
                category = self.env['budget.category'].browse(vals['budget_category_id'])
                if category.exists() and category.default_account_id:
                    vals['account_id'] = category.default_account_id.id

        return super().create(vals_list)

    # ВАЛІДАЦІЯ
    @api.constrains('planned_amount')
    def _check_planned_amount(self):
        """Перевірка планової суми"""
        for line in self:
            if line.planned_amount < 0:
                raise ValidationError(_("Планова сума не може бути від'ємною"))

    def name_get(self):
        """Кастомне відображення назви рядка"""
        result = []
        for record in self:
            name = f"{record.description} ({record.planned_amount:,.2f})"
            result.append((record.id, name))
        return result