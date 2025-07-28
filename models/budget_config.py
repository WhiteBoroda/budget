# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import ValidationError


class ResponsibilityCenter(models.Model):
    """Центри бюджетної відповідальності (ЦБО) - гнучка структура"""
    _name = 'budget.responsibility.center'
    _description = 'Центри бюджетної відповідальності'
    _order = 'cbo_type, sequence, name'

    name = fields.Char('Назва ЦБО', required=True)
    code = fields.Char('Код', required=True, size=10)
    budget_plan_ids = fields.One2many('budget.plan', 'cbo_id', string='Бюджетні плани')

    # Гнучка типологія замість жорсткої ієрархії
    cbo_type = fields.Selection([
        ('holding', 'Холдинг'),
        ('cluster', 'Кластер'),
        ('business_direction', 'Напрямок бізнесу'),
        ('brand', 'Бренд'),
        ('enterprise', 'Підприємство'),
        ('department', 'Департамент'),
        ('division', 'Управління'),
        ('office', 'Відділ'),
        ('team', 'Група/Команда'),
        ('project', 'Проект'),
        ('other', 'Інше')
    ], 'Тип ЦБО', required=True)

    # Рівні для бюджетного планування
    budget_level = fields.Selection([
        ('strategic', 'Стратегічний (Холдинг)'),
        ('tactical', 'Тактичний (Кластер/Напрямок)'),
        ('operational', 'Операційний (Підприємство/Департамент)'),
        ('functional', 'Функціональний (Відділ/Команда)')
    ], 'Рівень бюджетування', required=True)

    parent_id = fields.Many2one('budget.responsibility.center', 'Батьківський ЦБО')
    child_ids = fields.One2many('budget.responsibility.center', 'parent_id', 'Дочірні ЦБО')

    responsible_user_id = fields.Many2one('res.users', 'Відповідальний за бюджет')
    approver_user_id = fields.Many2one('res.users', 'Затверджувач бюджету')

    # Зв'язки з організаційною структурою

    company_ids = fields.Many2many('res.company', string='Підприємства')
    department_id = fields.Many2one('hr.department', 'Підрозділ')

    # Географічні та бізнес-атрибути
    country_id = fields.Many2one('res.country', 'Країна')
    region = fields.Char('Регіон')
    business_segment = fields.Char('Бізнес-сегмент')

    sequence = fields.Integer('Послідовність', default=10)
    active = fields.Boolean('Активний', default=True)

    # Налаштування бюджетування
    budget_type_ids = fields.Many2many(
        'budget.type',
        'cbo_budget_type_rel',
        'cbo_id',
        'budget_type_id',
        'Типи бюджетів'
    )

    auto_consolidation = fields.Boolean('Автоматична консолідація',
                                        help="Автоматично консолідувати бюджети дочірніх ЦБО")

    consolidation_method = fields.Selection([
        ('sum', 'Сума'),
        ('average', 'Середнє'),
        ('weighted', 'Зважене середнє'),
        ('custom', 'Користувацький метод')
    ], 'Метод консолідації', default='sum')

    @api.constrains('parent_id')
    def _check_hierarchy(self):
        """Перевірка на рекурсивну ієрархію"""
        for record in self:
            if record.parent_id:
                if record.parent_id.id == record.id:
                    raise ValidationError('ЦБО не може бути батьківським для самого себе!')

                parent = record.parent_id
                visited = set()
                while parent:
                    if parent.id in visited:
                        raise ValidationError('Неможливо створити рекурсивну ієрархію ЦБО!')
                    if parent.id == record.id:
                        raise ValidationError('Неможливо створити рекурсивну ієрархію ЦБО!')
                    visited.add(parent.id)
                    parent = parent.parent_id

    @api.depends('name', 'code', 'cbo_type')
    def _compute_display_name(self):
        for record in self:
            type_name = dict(record._fields['cbo_type'].selection).get(record.cbo_type, '')
            record.display_name = f"[{record.code}] {record.name} ({type_name})"

    def get_all_children(self, include_self=True):
        """Отримати всі дочірні ЦБО рекурсивно"""
        children = self.env['budget.responsibility.center']
        if include_self:
            children |= self

        for child in self.child_ids:
            children |= child.get_all_children(include_self=True)

        return children

    def get_consolidation_scope(self):
        """Отримати область консолідації для цього ЦБО"""
        if self.auto_consolidation:
            return self.get_all_children(include_self=False)
        return self.env['budget.responsibility.center']


class BudgetType(models.Model):
    """Типи бюджетів згідно регламенту"""
    _name = 'budget.type'
    _description = 'Типи бюджетів'
    _order = 'code'

    name = fields.Char('Назва бюджету', required=True)
    code = fields.Char('Код бюджету', required=True, size=10)
    description = fields.Text('Опис')

    budget_category = fields.Selection([
        ('income', 'Доходи'),
        ('direct_costs', 'Прямі витрати'),
        ('indirect_costs', 'Непрямі витрати'),
        ('administrative', 'Адміністративні витрати'),
        ('investment', 'Інвестиційні витрати'),
        ('financial', 'Фінансові операції')
    ], 'Категорія бюджету', required=True, default='administrative')

    calculation_method = fields.Selection([
        ('manual', 'Ручне планування'),
        ('norm_based', 'На основі нормативів'),
        ('statistical', 'Статистичний метод'),
        ('contract_based', 'На основі договорів'),
        ('sales_percentage', 'Відсоток від продажів')
    ], 'Метод розрахунку', default='manual')

    # Гнучкість застосування
    applicable_cbo_types = fields.Selection([
        ('all', 'Всі типи ЦБО'),
        ('enterprises_only', 'Тільки підприємства'),
        ('departments_only', 'Тільки департаменти'),
        ('custom', 'Налаштування вручну')
    ], 'Застосовність', default='all')

    responsible_cbo_ids = fields.Many2many(
        'budget.responsibility.center',
        'cbo_budget_type_rel',
        'budget_type_id',
        'cbo_id',
        'Відповідальні ЦБО'
    )

    approval_required = fields.Boolean('Потребує затвердження', default=True)

    # Налаштування для різних рівнів
    level_settings = fields.One2many('budget.type.level.setting', 'budget_type_id',
                                     'Налаштування по рівнях')

    sequence = fields.Integer('Послідовність', default=10)
    active = fields.Boolean('Активний', default=True)
    category_ids = fields.Many2many('budget.category', 'budget_type_category_rel',
                                    'budget_type_id', 'category_id', 'Категорії')


class BudgetTypeLevelSetting(models.Model):
    """Налаштування типу бюджету для різних рівнів ЦБО"""
    _name = 'budget.type.level.setting'
    _description = 'Налаштування типу бюджету по рівнях'

    budget_type_id = fields.Many2one('budget.type', 'Тип бюджету', required=True)
    budget_level = fields.Selection([
        ('strategic', 'Стратегічний'),
        ('tactical', 'Тактичний'),
        ('operational', 'Операційний'),
        ('functional', 'Функціональний')
    ], 'Рівень бюджетування', required=True)

    is_required = fields.Boolean('Обов\'язковий', default=True)
    calculation_method = fields.Selection([
        ('manual', 'Ручне планування'),
        ('norm_based', 'На основі нормативів'),
        ('statistical', 'Статистичний метод'),
        ('contract_based', 'На основі договорів'),
        ('sales_percentage', 'Відсоток від продажів'),
        ('consolidation', 'Консолідація з нижчих рівнів')
    ], 'Метод розрахунку')

    deadline_days = fields.Integer('Дедлайн (днів до кінця періоду)', default=15)
    approval_workflow = fields.Selection([
        ('simple', 'Простий (1 рівень)'),
        ('two_level', 'Дворівневий'),
        ('complex', 'Складний (3+ рівні)')
    ], 'Workflow затвердження', default='simple')


class BudgetPeriod(models.Model):
    """Бюджетні періоди"""
    _name = 'budget.period'
    _description = 'Бюджетні періоди'
    _order = 'date_start desc'

    name = fields.Char('Назва періоду', required=True)
    date_start = fields.Date('Дата початку', required=True)
    date_end = fields.Date('Дата закінчення', required=True)

    period_type = fields.Selection([
        ('month', 'Місяць'),
        ('quarter', 'Квартал'),
        ('year', 'Рік'),
        ('custom', 'Довільний період')
    ], 'Тип періоду', required=True, default='month')

    state = fields.Selection([
        ('draft', 'Чернетка'),
        ('planning', 'Планування'),
        ('approved', 'Затверджений'),
        ('closed', 'Закритий')
    ], 'Статус', default='draft', required=True)

    company_ids = fields.Many2many('res.company', 'Компанії',
                                   default=lambda self: [(6, 0, [self.env.company.id])],
                                   required=True)
    company_id = fields.Many2one('res.company', 'Головна компанія',
                                 compute='_compute_company_id', store=True)

    @api.depends('company_ids')
    def _compute_company_id(self):
        for record in self:
            record.company_id = record.company_ids[0] if record.company_ids else self.env.company

    # Гнучкість для різних циклів планування
    planning_cycle = fields.Selection([
        ('annual', 'Річне планування'),
        ('quarterly', 'Квартальне планування'),
        ('monthly', 'Місячне планування'),
        ('rolling', 'Rolling forecast'),
        ('project', 'Проектне планування')
    ], 'Цикл планування', default='monthly')

    is_forecast = fields.Boolean('Прогнозний період',
                                 help="Період для прогнозів, а не фактичного виконання")

    active = fields.Boolean('Активний', default=True)

    @api.constrains('date_start', 'date_end')
    def _check_dates(self):
        for record in self:
            if record.date_start >= record.date_end:
                raise ValidationError('Дата початку має бути менше дати закінчення!')


class BudgetCurrency(models.Model):
    """Валютні налаштування для бюджетування"""
    _name = 'budget.currency.setting'
    _description = 'Валютні налаштування бюджету'
    _rec_name = 'name'

    name = fields.Char('Назва налаштування', required=True, compute='_compute_name', store=True)
    base_currency_id = fields.Many2one('res.currency', 'Базова валюта', required=True)
    reporting_currency_id = fields.Many2one('res.currency', 'Валюта звітності')

    # Курси для планування
    planning_rate = fields.Float('Плановий курс', digits=(12, 6))
    use_planned_rates = fields.Boolean('Використовувати планові курси',
                                       help="Використовувати фіксовані курси для планування")

    cbo_ids = fields.Many2many('budget.responsibility.center',
                               string='ЦБО',
                               help="ЦБО які використовують ці налаштування")

    cbo_count = fields.Integer('Кількість ЦБО', compute='_compute_cbo_count', store=True)

    active = fields.Boolean('Активний', default=True)

    @api.depends('base_currency_id', 'reporting_currency_id')
    def _compute_name(self):
        """Автоматичне формування назви"""
        for record in self:
            if record.base_currency_id:
                name = f"Налаштування {record.base_currency_id.name}"
                if record.reporting_currency_id and record.reporting_currency_id != record.base_currency_id:
                    name += f" → {record.reporting_currency_id.name}"
                record.name = name
            else:
                record.name = "Нове налаштування"

    @api.depends('cbo_ids')
    def _compute_cbo_count(self):
        """Підрахунок кількості ЦБО"""
        for record in self:
            record.cbo_count = len(record.cbo_ids)

    @api.onchange('base_currency_id', 'reporting_currency_id')
    def _onchange_currencies(self):
        """При зміні валют пересчитуємо плановий курс"""
        if self.base_currency_id and self.reporting_currency_id and self.base_currency_id != self.reporting_currency_id:
            # Можна додати логіку отримання поточного курсу
            pass

    @api.constrains('planning_rate')
    def _check_planning_rate(self):
        """Перевірка планового курсу"""
        for record in self:
            if record.use_planned_rates and record.planning_rate <= 0:
                raise ValidationError('Плановий курс повинен бути більше нуля!')


class BudgetLog(models.Model):
    """Логування дій в системі бюджетування"""
    _name = 'budget.log'
    _description = 'Лог дій бюджетування'
    _order = 'create_date desc'

    model_name = fields.Char('Модель', required=True)
    record_id = fields.Integer('ID запису', required=True)
    action = fields.Char('Дія', required=True)
    description = fields.Text('Опис')
    user_id = fields.Many2one('res.users', 'Користувач', required=True)
    create_date = fields.Datetime('Дата створення', default=fields.Datetime.now)

    def name_get(self):
        result = []
        for record in self:
            name = f"{record.action} - {record.model_name} ({record.create_date})"
            result.append((record.id, name))
        return result