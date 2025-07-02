# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import ValidationError
import logging, json

_logger = logging.getLogger('budget.models')



class BudgetPlan(models.Model):
    """Основний документ бюджетного планування"""
    _name = 'budget.plan'
    _description = 'Бюджетний план'
    _order = 'period_id desc, cbo_id, budget_type_id'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # Автонумерація
    name = fields.Char('Номер', required=True, copy=False, readonly=True, default='/')

    def _compute_display_name(self):
        for record in self:
            if record.budget_type_id and record.cbo_id and record.period_id:
                budget_type_name = record.budget_type_id.name
                cbo_name = record.cbo_id.name
                period_name = record.period_id.name
                record.display_name = f"{budget_type_name} - {cbo_name} ({period_name})"
            elif record.name and record.name != '/':
                record.display_name = record.name
            else:
                record.display_name = "Новий бюджет"

    display_name = fields.Char('Назва', compute='_compute_display_name', store=True)

    # Основні параметри
    period_id = fields.Many2one('budget.period', 'Період', required=True, index=True)
    cbo_id = fields.Many2one('budget.responsibility.center', 'ЦБО', required=True, index=True)
    budget_type_id = fields.Many2one('budget.type', 'Тип бюджету', required=True, index=True)

    # Автоматичне визначення рівня на основі ЦБО
    budget_level = fields.Selection(related='cbo_id.budget_level', store=True, readonly=True)

    cbo_domain = fields.Char(
        string='Домен ЦБО',
        compute='_compute_cbo_domain',
        store=False
    )

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

            # Фільтр по типу бюджету (якщо в типі бюджету є обмеження на ЦБО)
            if record.budget_type_id and hasattr(record.budget_type_id, 'allowed_cbo_types'):
                if record.budget_type_id.allowed_cbo_types:
                    domain.append(('cbo_type', 'in', record.budget_type_id.allowed_cbo_types))

            # Перетворюємо домен у JSON строку для використання в представленнях
            record.cbo_domain = json.dumps(domain)

    # ИСПРАВЛЕНО для Odoo 17: убираем states из поля state
    state = fields.Selection([
        ('draft', 'Чернетка'),
        ('planning', 'Планування'),
        ('coordination', 'Узгодження'),
        ('approved', 'Затверджений'),
        ('revision', 'Доопрацювання'),
        ('executed', 'Виконується'),
        ('closed', 'Закритий')
    ], 'Статус', default='draft', required=True, tracking=True, index=True)

    # ИСПРАВЛЕНО для Odoo 17: убираем states из финансовых полей
    planned_amount = fields.Monetary('Планова сума', compute='_compute_totals', store=True,
                                     currency_field='currency_id')
    actual_amount = fields.Monetary('Фактична сума', compute='_compute_actual_amount', store=True,
                                    currency_field='currency_id')
    committed_amount = fields.Monetary('Зарезервована сума', compute='_compute_committed_amount', store=True,
                                       currency_field='currency_id')
    available_amount = fields.Monetary('Доступна сума', compute='_compute_available_amount', store=True,
                                       currency_field='currency_id')

    variance_amount = fields.Monetary('Відхилення', compute='_compute_variance', store=True,
                                      currency_field='currency_id')
    variance_percent = fields.Float('Відхилення, %', compute='_compute_variance', store=True)
    execution_percent = fields.Float('Виконання, %', compute='_compute_execution', store=True)

    # Відповідальні особи
    responsible_user_id = fields.Many2one('res.users', 'Відповідальний планувальник',
                                          required=True, default=lambda self: self.env.user, index=True)
    coordinator_user_id = fields.Many2one('res.users', 'Координатор')
    approver_user_id = fields.Many2one('res.users', 'Затверджувач')
    approved_by_id = fields.Many2one('res.users', 'Затверджено')

    # Організаційні зв'язки
    company_id = fields.Many2one('res.company', 'Підприємство', required=True,
                                 default=lambda self: self.env.company, index=True)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id', readonly=True)

    # Зв'язок з прогнозами продажів (замість sales_plan_id)
    sales_forecast_ids = fields.Many2many('sale.forecast', string='Прогнози продажів',
                                          domain="[('period_id', '=', period_id), ('state', '=', 'approved')]")

    # Лінії бюджету
    line_ids = fields.One2many('budget.plan.line', 'plan_id', 'Позиції бюджету')

    # Консолідація та ієрархія
    parent_budget_id = fields.Many2one('budget.plan', 'Батьківський бюджет')
    child_budget_ids = fields.One2many('budget.plan', 'parent_budget_id', 'Дочірні бюджети')

    # Автоматична консолідація
    auto_consolidation = fields.Boolean(related='cbo_id.auto_consolidation', readonly=True)
    consolidation_method = fields.Selection(related='cbo_id.consolidation_method', readonly=True)

    # Метадані планування
    submission_deadline = fields.Date('Крайній термін подання', required=True, default=fields.Date.today)
    approval_date = fields.Datetime('Дата затвердження')

    # Налаштування версійності
    version = fields.Char('Версія', default='1.0')
    is_baseline = fields.Boolean('Базова версія', help="Затверджена базова версія бюджету")
    baseline_budget_id = fields.Many2one('budget.plan', 'Базовий бюджет')

    # Додаткові налаштування
    calculation_method = fields.Selection(related='budget_type_id.calculation_method', readonly=True)

    # Валютні налаштування
    budget_currency_setting_id = fields.Many2one('budget.currency.setting', 'Валютні налаштування')

    notes = fields.Text('Примітки та обґрунтування')

    # ДОБАВЛЕНО для Odoo 17: computed поля вместо states

    @api.depends('state')
    def _compute_is_readonly(self):
        """Определяет можно ли редактировать бюджет"""
        for plan in self:
            plan.is_readonly = plan.state in ['approved', 'executed', 'closed']

    is_readonly = fields.Boolean('Тільки для читання', compute='_compute_is_readonly')

    @api.depends('state')
    def _compute_can_edit_lines(self):
        """Определяет можно ли редактировать строки бюджета"""
        for plan in self:
            plan.can_edit_lines = plan.state in ['draft', 'planning', 'revision']

    can_edit_lines = fields.Boolean('Можна редагувати позиції', compute='_compute_can_edit_lines')

    @api.model
    def create(self, vals_list):
        """Створення планів бюджету з підтримкою batch операцій"""
        # Перетворюємо в список якщо переданий словник
        if isinstance(vals_list, dict):
            vals_list = [vals_list]

        # Обробляємо кожен запис
        for vals in vals_list:
            # Автогенерація номера з послідовності
            if vals.get('name', '/') == '/':
                vals['name'] = self.env['ir.sequence'].next_by_code('budget.plan') or '/'

            # Автогенерація назви якщо не вказана display_name
            if not vals.get('display_name'):
                vals['display_name'] = self._generate_budget_name(vals)

            # Валідація обов'язкових полів
            required_fields = ['period_id', 'budget_type_id', 'cbo_id']
            for field in required_fields:
                if not vals.get(field):
                    field_name = self._fields[field].string
                    raise ValidationError(f'Поле "{field_name}" є обов\'язковим')

            # Перевірка унікальності бюджету
            existing = self.search([
                ('period_id', '=', vals['period_id']),
                ('budget_type_id', '=', vals['budget_type_id']),
                ('cbo_id', '=', vals['cbo_id']),
                ('state', '!=', 'draft')
            ])
            if existing:
                raise ValidationError(
                    'Для цього ЦБО вже існує затверджений бюджет даного типу в цьому періоді'
                )

            # Встановлення значень за замовчуванням
            if not vals.get('company_id'):
                if vals.get('cbo_id'):
                    cbo = self.env['budget.responsibility.center'].browse(vals['cbo_id'])
                    if cbo.exists() and cbo.company_id:
                        vals['company_id'] = cbo.company_id.id
                    else:
                        vals['company_id'] = self.env.company.id
                else:
                    vals['company_id'] = self.env.company.id

            if not vals.get('responsible_user_id'):
                vals['responsible_user_id'] = self.env.user.id

            if not vals.get('state'):
                vals['state'] = 'draft'

            if not vals.get('submission_deadline'):
                vals['submission_deadline'] = fields.Date.today()

        # Створення записів
        budgets = super().create(vals_list)

        # Пост-обробка для кожного створеного бюджету
        for budget in budgets:
            # Логування
            self.env['budget.log'].sudo().create({
                'model_name': 'budget.plan',
                'record_id': budget.id,
                'action': 'create',
                'description': f'Створено план бюджету: {budget.display_name}',
                'user_id': self.env.user.id
            })

            # Повідомлення в чаттері
            budget.message_post(
                body=f"📊 Створено новий план бюджету {budget.budget_type_id.name} для {budget.cbo_id.name}",
                message_type='notification'
            )

            # Автоматична консолідація якщо налаштована
            if budget.cbo_id.auto_consolidation and budget.cbo_id.parent_id:
                budget._create_consolidation_budget()

        return budgets

    def _generate_budget_name(self, vals):
        """Генерація назви бюджету"""
        budget_type_name = "Бюджет"
        period_name = "Період"
        cbo_name = "ЦБО"

        # Отримуємо назву типу бюджету
        if vals.get('budget_type_id'):
            budget_type = self.env['budget.type'].browse(vals['budget_type_id'])
            budget_type_name = budget_type.name if budget_type.exists() else "Бюджет"

        # Отримуємо назву періоду
        if vals.get('period_id'):
            period = self.env['budget.period'].browse(vals['period_id'])
            period_name = period.name if period.exists() else "Період"

        # Отримуємо назву ЦБО
        if vals.get('cbo_id'):
            cbo = self.env['budget.responsibility.center'].browse(vals['cbo_id'])
            cbo_name = cbo.name if cbo.exists() else "ЦБО"

        return f"{budget_type_name} - {cbo_name} - {period_name}"

    def _validate_budget_data(self, vals):
        """Валідація даних бюджету"""
        # Перевірка періоду
        if vals.get('period_id'):
            period = self.env['budget.period'].browse(vals['period_id'])
            if not period.exists():
                raise ValidationError("Вказаний період не існує")
            if period.state == 'closed':
                raise ValidationError("Неможливо створити бюджет для закритого періоду")

        # Перевірка типу бюджету
        if vals.get('budget_type_id'):
            budget_type = self.env['budget.type'].browse(vals['budget_type_id'])
            if not budget_type.exists():
                raise ValidationError("Вказаний тип бюджету не існує")

        # Перевірка ЦБО
        if vals.get('cbo_id'):
            cbo = self.env['budget.responsibility.center'].browse(vals['cbo_id'])
            if not cbo.exists():
                raise ValidationError("Вказане ЦБО не існує")

        # Перевірка унікальності (одн бюджет одного типу для ЦБО в періоді)
        if vals.get('period_id') and vals.get('budget_type_id') and vals.get('cbo_id'):
            existing = self.search([
                ('period_id', '=', vals['period_id']),
                ('budget_type_id', '=', vals['budget_type_id']),
                ('cbo_id', '=', vals['cbo_id']),
                ('state', '!=', 'draft')  # Дозволяємо кілька чернеток
            ])
            if existing:
                raise ValidationError(
                    "Для цього ЦБО вже існує затверджений бюджет даного типу в цьому періоді"
                )

    def _set_budget_defaults(self, vals):
        """Встановлення значень за замовчуванням для бюджету"""
        # Встановлення компанії за замовчуванням
        if not vals.get('company_id'):
            if vals.get('cbo_id'):
                cbo = self.env['budget.responsibility.center'].browse(vals['cbo_id'])
                if cbo.exists() and cbo.company_ids:
                    vals['company_id'] = cbo.company_ids.id
                else:
                    vals['company_id'] = self.env.company.id
            else:
                vals['company_id'] = self.env.company.id

    def _post_create_budget_actions(self):
        """Дії після створення бюджету"""
        # Логування створення
        _logger.info(f'Створено план бюджету: {self.name} (ID: {self.id})')

        # Повідомлення в чаттері
        self.message_post(
            body=f"📊 Створено новий план бюджету {self.budget_type_id.name} для {self.cbo_id.name}",
            message_type='notification'
        )

        # Автоматична консолідація (якщо налаштована)
        if self.cbo_id.auto_consolidation and self.cbo_id.parent_id:
            self._create_consolidation_budget()

        # Створення базових категорій (якщо потрібно)
        if not self.line_ids and hasattr(self, '_create_default_budget_lines'):
            self._create_default_budget_lines()

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
                'state': 'draft'
            }
            consolidated_budget = self.create(consolidated_vals)

        # Прив'язка до консолідованого бюджету
        self.parent_budget_id = consolidated_budget.id


    @api.depends('line_ids.planned_amount')
    def _compute_totals(self):
        for record in self:
            record.planned_amount = sum(record.line_ids.mapped('planned_amount'))

    @api.depends('line_ids.actual_amount')
    def _compute_actual_amount(self):
        for record in self:
            # Отримуємо фактичні витрати з execution records
            executions = self.env['budget.execution'].search([('budget_plan_id', '=', record.id)])
            record.actual_amount = sum(executions.mapped('actual_amount'))

    @api.depends('line_ids.committed_amount')
    def _compute_committed_amount(self):
        for record in self:
            record.committed_amount = sum(record.line_ids.mapped('committed_amount'))

    @api.depends('planned_amount', 'actual_amount', 'committed_amount')
    def _compute_available_amount(self):
        for record in self:
            record.available_amount = record.planned_amount - record.actual_amount - record.committed_amount

    @api.depends('planned_amount', 'actual_amount')
    def _compute_variance(self):
        for record in self:
            record.variance_amount = record.actual_amount - record.planned_amount
            if record.planned_amount:
                record.variance_percent = (record.variance_amount / record.planned_amount) * 100
            else:
                record.variance_percent = 0.0

    @api.depends('planned_amount', 'actual_amount')
    def _compute_execution(self):
        for record in self:
            if record.planned_amount:
                record.execution_percent = (record.actual_amount / record.planned_amount) * 100
            else:
                record.execution_percent = 0.0

    @api.onchange('cbo_id')
    def _onchange_cbo_id(self):
        """Автоматичне встановлення координатора та затверджувача"""
        if self.cbo_id:
            self.coordinator_user_id = self.cbo_id.responsible_user_id
            self.approver_user_id = self.cbo_id.approver_user_id

    @api.onchange('budget_type_id', 'cbo_id')
    def _onchange_budget_type_cbo(self):
        """Встановлення дедлайну на основі налаштувань типу бюджету"""
        if self.budget_type_id and self.cbo_id and self.period_id:
            level_setting = self.env['budget.type.level.setting'].search([
                ('budget_type_id', '=', self.budget_type_id.id),
                ('budget_level', '=', self.cbo_id.budget_level)
            ], limit=1)

            if level_setting and level_setting.deadline_days:
                from datetime import timedelta
                self.submission_deadline = self.period_id.date_end - timedelta(days=level_setting.deadline_days)

    def action_start_planning(self):
        """Початок планування"""
        self.state = 'planning'
        self.message_post(body="Розпочато планування бюджету")

    def action_send_coordination(self):
        """Відправка на узгодження"""
        if not self.line_ids:
            raise ValidationError('Неможливо відправити порожній бюджет на узгодження!')

        self.state = 'coordination'
        self.message_post(body="Бюджет відправлено на узгодження")

        # Сповіщення координатора
        if self.coordinator_user_id:
            self.activity_schedule(
                'mail.mail_activity_data_todo',
                user_id=self.coordinator_user_id.id,
                summary=f'Узгодження бюджету: {self.display_name}'
            )

    def action_approve(self):
        """Затвердження бюджету"""
        self.write({
            'state': 'approved',
            'approved_by_id': self.env.user.id,
            'approval_date': fields.Datetime.now(),
            'is_baseline': True
        })
        self.message_post(body="Бюджет затверджено")

        # Автоматична консолідація якщо налаштована
        if self.auto_consolidation:
            self._trigger_consolidation()

    def action_request_revision(self):
        """Відправка на доопрацювання"""
        self.state = 'revision'
        self.message_post(body="Бюджет відправлено на доопрацювання")

        # Сповіщення відповідального
        if self.responsible_user_id:
            self.activity_schedule(
                'mail.mail_activity_data_todo',
                user_id=self.responsible_user_id.id,
                summary=f'Доопрацювання бюджету: {self.display_name}'
            )

    def action_execute(self):
        """Початок виконання бюджету"""
        if self.state != 'approved':
            raise ValidationError('Можна виконувати тільки затверджені бюджети!')
        self.state = 'executed'

    def action_close(self):
        """Закриття бюджету"""
        self.state = 'closed'

    def action_create_revision(self):
        """Створення ревізії бюджету"""
        new_version = self.copy({
            'name': '/',
            'version': f"{self.version}.rev",
            'state': 'draft',
            'is_baseline': False,
            'baseline_budget_id': self.id,
            'approved_by_id': False,
            'approval_date': False,
        })

        return {
            'type': 'ir.actions.act_window',
            'name': 'Ревізія бюджету',
            'res_model': 'budget.plan',
            'res_id': new_version.id,
            'view_mode': 'form',
            'target': 'current'
        }

    def _trigger_consolidation(self):
        """Автоматична консолідація з дочірніх ЦБО"""
        if not self.cbo_id.parent_id:
            return  # Це вже верхній рівень

        parent_cbo = self.cbo_id.parent_id

        # Перевіряємо чи існує батьківський бюджет
        parent_budget = self.env['budget.plan'].search([
            ('period_id', '=', self.period_id.id),
            ('cbo_id', '=', parent_cbo.id),
            ('budget_type_id', '=', self.budget_type_id.id)
        ], limit=1)

        if not parent_budget:
            # Створюємо батьківський бюджет
            parent_budget = self.env['budget.plan'].create({
                'period_id': self.period_id.id,
                'cbo_id': parent_cbo.id,
                'budget_type_id': self.budget_type_id.id,
                'state': 'planning',
                'responsible_user_id': parent_cbo.responsible_user_id.id or self.env.user.id,
                'submission_deadline': self.submission_deadline,
                'notes': f'Автоматично створено шляхом консолідації з {self.cbo_id.name}'
            })

        # Зв'язуємо як дочірній
        self.parent_budget_id = parent_budget.id

        # Консолідуємо суми
        parent_budget._consolidate_child_budgets()

    def _consolidate_child_budgets(self):
        """Консолідація дочірніх бюджетів"""
        if not self.child_budget_ids:
            return

        # Очищуємо існуючі лінії консолідації
        consolidation_lines = self.line_ids.filtered(lambda l: l.is_consolidation)
        consolidation_lines.unlink()

        # Групуємо лінії дочірніх бюджетів
        consolidated_data = {}

        for child_budget in self.child_budget_ids.filtered(lambda b: b.state == 'approved'):
            for line in child_budget.line_ids:
                key = (line.account_id.id, line.analytic_account_id.id, line.description)

                if key not in consolidated_data:
                    consolidated_data[key] = {
                        'account_id': line.account_id.id,
                        'analytic_account_id': line.analytic_account_id.id,
                        'description': f"Консолідація: {line.description}",
                        'planned_amount': 0,
                        'is_consolidation': True
                    }

                consolidated_data[key]['planned_amount'] += line.planned_amount

        # Створюємо консолідовані лінії
        for line_data in consolidated_data.values():
            line_data['plan_id'] = self.id
            self.env['budget.plan.line'].create(line_data)


class BudgetPlanLine(models.Model):
    """Позиції бюджетного плану"""
    _name = 'budget.plan.line'
    _description = 'Позиції бюджетного плану'

    plan_id = fields.Many2one('budget.plan', 'Бюджетний план', required=True, ondelete='cascade')

    # Рахунки
    account_id = fields.Many2one('account.account', 'Рахунок')
    analytic_account_id = fields.Many2one('account.analytic.account', 'Аналітичний рахунок')

    description = fields.Char('Опис', required=True)

    # ИСПРАВЛЕНО для Odoo 17: убираем states из финансовых полей
    planned_amount = fields.Monetary('Планова сума', required=True, currency_field='currency_id')
    committed_amount = fields.Monetary('Зарезервована сума', currency_field='currency_id')
    actual_amount = fields.Monetary('Фактична сума', compute='_compute_actual_amount', store=True,
                                    currency_field='currency_id')

    # Розрахунки
    calculation_basis = fields.Text('Основа розрахунку')
    calculation_method = fields.Selection([
        ('manual', 'Ручний ввід'),
        ('norm_based', 'За нормативами'),
        ('percentage', 'Відсоток від доходів'),
        ('previous_period', 'На основі попереднього періоду'),
        ('sales_forecast', 'На основі прогнозу продажів'),
        ('consolidation', 'Консолідація')
    ], 'Метод розрахунку', default='manual')

    # Деталізація для розрахунків
    quantity = fields.Float('Кількість')
    unit_price = fields.Monetary('Ціна за одиницю', currency_field='currency_id')
    percentage_base = fields.Float('Відсоток від бази')

    # Прив'язка до прогнозу продажів
    sales_forecast_line_id = fields.Many2one('sale.forecast.line', 'Лінія прогнозу продажів')

    currency_id = fields.Many2one('res.currency', related='plan_id.company_id.currency_id', readonly=True)

    # Аналітичні виміри
    department_id = fields.Many2one('hr.department', 'Підрозділ')
    project_id = fields.Many2one('project.project', 'Проект')

    # Службові поля
    is_consolidation = fields.Boolean('Консолідаційна лінія', default=False)

    notes = fields.Text('Примітки')

    # ДОБАВЛЕНО для Odoo 17: computed поля вместо states
    @api.depends('plan_id.state')
    def _compute_is_editable(self):
        """Определяет можно ли редактировать строку"""
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
