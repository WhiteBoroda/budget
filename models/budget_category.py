# -*- coding: utf-8 -*-
# models/budget_category.py - НОВА МОДЕЛЬ

from odoo import models, fields, api


class BudgetCategory(models.Model):
    """Категорії бюджетних витрат (замість прямих рахунків)"""
    _name = 'budget.category'
    _description = 'Категорія бюджетних витрат'
    _order = 'sequence, code, name'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char('Назва категорії', required=True, tracking=True)
    code = fields.Char('Код', required=True, size=20, tracking=True)
    description = fields.Text('Опис', tracking=True)

    # Ієрархія категорій
    parent_id = fields.Many2one('budget.category', 'Батьківська категорія', tracking=True)
    child_ids = fields.One2many('budget.category', 'parent_id', 'Підкategорії')

    # Прив'язка до типів бюджетів
    budget_type_ids = fields.Many2many('budget.type', string='Типи бюджетів', tracking=True)

    # Налаштування
    sequence = fields.Integer('Послідовність', default=10)
    active = fields.Boolean('Активна', default=True, tracking=True)
    company_id = fields.Many2one('res.company', 'Підприємство',
                                 default=lambda self: self.env.company, tracking=True)

    # Опціональне зопоставлення з обліковими рахунками
    default_account_id = fields.Many2one('account.account', 'Рахунок за замовчуванням', tracking=True)
    account_mapping_ids = fields.One2many('budget.category.account.mapping',
                                          'category_id', 'Зопоставлення рахунків')

    @api.depends('name', 'code')
    def _compute_display_name(self):
        for record in self:
            record.display_name = f"[{record.code}] {record.name}"

    def name_get(self):
        result = []
        for record in self:
            name = f"[{record.code}] {record.name}"
            if record.parent_id:
                name = f"{record.parent_id.name} / {name}"
            result.append((record.id, name))
        return result


class BudgetCategoryAccountMapping(models.Model):
    """Зопоставлення категорій бюджету з обліковими рахунками"""
    _name = 'budget.category.account.mapping'
    _description = 'Зопоставлення категорії бюджету з рахунками'

    category_id = fields.Many2one('budget.category', 'Категорія бюджету', required=True)

    # Умови зопоставлення
    company_id = fields.Many2one('res.company', 'Підприємство')
    cbo_id = fields.Many2one('budget.responsibility.center', 'ЦБО')
    cost_center_id = fields.Many2one('budget.cost.center', 'Центр витрат')

    # Рахунки
    account_id = fields.Many2one('account.account', 'Рахунок обліку', required=False)
    analytic_account_id = fields.Many2one('account.analytic.account', 'Аналітичний рахунок')

    # Пріоритет (для вибору при кількох відповідностях)
    priority = fields.Integer('Пріоритет', default=10)
    active = fields.Boolean('Активне', default=True)


class BudgetCostCenter(models.Model):
    """Центри витрат (спрощена аналітика)"""
    _name = 'budget.cost.center'
    _description = 'Центр витрат'
    _order = 'sequence, code, name'

    name = fields.Char('Назва центру витрат', required=True)
    code = fields.Char('Код', required=True, size=20)
    description = fields.Text('Опис')

    # Зв'язки з організаційною структурою
    cbo_id = fields.Many2one('budget.responsibility.center', 'ЦБО')
    company_id = fields.Many2one('res.company', 'Підприємство',
                                 default=lambda self: self.env.company)
    department_id = fields.Many2one('hr.department', 'Підрозділ')

    # Налаштування
    sequence = fields.Integer('Послідовність', default=10)
    active = fields.Boolean('Активний', default=True)

    # Опціональне зопоставлення з аналітичними рахунками
    analytic_account_id = fields.Many2one('account.analytic.account',
                                          'Аналітичний рахунок за замовчуванням')

    @api.depends('name', 'code')
    def _compute_display_name(self):
        for record in self:
            record.display_name = f"[{record.code}] {record.name}"


class BudgetPlanLine(models.Model):
    """Оновлена лінія бюджету з категоріями"""
    _inherit = 'budget.plan.line'

    # ЗАМІНЮЄМО рахунки на категорії
    budget_category_id = fields.Many2one('budget.category', 'Категорія витрат',
                                         required=True)
    cost_center_id = fields.Many2one('budget.cost.center', 'Центр витрат')

    # Рахунки стають необов'язковими та обчислюваними
    account_id = fields.Many2one('account.account', 'Рахунок обліку',
                                 compute='_compute_accounting_data',
                                 store=True, readonly=False)
    analytic_account_id = fields.Many2one('account.analytic.account',
                                          'Аналітичний рахунок',
                                          compute='_compute_accounting_data',
                                          store=True, readonly=False)

    # Додаткові поля для зручності
    category_code = fields.Char(related='budget_category_id.code', string='Код категорії')
    cost_center_code = fields.Char(related='cost_center_id.code', string='Код центру витрат')

    @api.depends('budget_category_id', 'cost_center_id', 'plan_id.company_ids', 'plan_id.cbo_id')
    def _compute_accounting_data(self):
        """Автоматичне визначення рахунків на основі зопоставлень"""
        for line in self:
            if not line.budget_category_id:
                line.account_id = False
                line.analytic_account_id = False
                continue

            # Шукаємо найкращу відповідність
            mapping = self._find_best_account_mapping(line)

            if mapping:
                line.account_id = mapping.account_id
                line.analytic_account_id = mapping.analytic_account_id
            else:
                # Використовуємо рахунки за замовчуванням
                line.account_id = line.budget_category_id.default_account_id
                line.analytic_account_id = line.cost_center_id.analytic_account_id if line.cost_center_id else False

    def _find_best_account_mapping(self, line):
        """Знаходження найкращого зопоставлення рахунків"""
        domain = [
            ('category_id', '=', line.budget_category_id.id),
            ('active', '=', True)
        ]

        # Додаємо умови для більш точного пошуку
        if line.plan_id.company_id:
            domain.append(('company_id', 'in', [False, line.plan_id.company_id.id]))

        if line.plan_id.cbo_id:
            domain.append(('cbo_id', 'in', [False, line.plan_id.cbo_id.id]))

        if line.cost_center_id:
            domain.append(('cost_center_id', 'in', [False, line.cost_center_id.id]))

        # Шукаємо з найвищим пріоритетом
        mappings = self.env['budget.category.account.mapping'].search(
            domain, order='priority desc, id desc', limit=1
        )

        return mappings[0] if mappings else None

    @api.onchange('budget_category_id')
    def _onchange_budget_category_id(self):
        """Автозаповнення опису при виборі категорії"""
        if self.budget_category_id:
            if not self.description:
                self.description = self.budget_category_id.name

    @api.onchange('cost_center_id')
    def _onchange_cost_center_id(self):
        """Оновлення аналітичного рахунку при зміні центру витрат"""
        if self.cost_center_id and self.cost_center_id.analytic_account_id:
            self.analytic_account_id = self.cost_center_id.analytic_account_id


class BudgetPlan(models.Model):
    """Розширення бюджетного плану"""
    _inherit = 'budget.plan'

    def action_update_accounting_data(self):
        """Дія для оновлення облікових даних всіх ліній"""
        for line in self.line_ids:
            line._compute_accounting_data()

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Оновлено',
                'message': 'Облікові дані оновлено згідно з поточними зопоставленнями',
                'type': 'success',
            }
        }