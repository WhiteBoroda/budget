# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import ValidationError


class ResponsibilityCenter(models.Model):
    """Центри бюджетної відповідальності (ЦБО)"""
    _name = 'budget.responsibility.center'
    _description = 'Центри бюджетної відповідальності'
    _order = 'level, sequence, name'

    name = fields.Char('Назва ЦБО', required=True)
    code = fields.Char('Код', required=True, size=10)
    level = fields.Selection([
        ('managing_company', 'Управляюча компанія'),
        ('production_enterprise', 'Виробниче підприємство')
    ], 'Рівень', required=True)

    parent_id = fields.Many2one('budget.responsibility.center', 'Батьківський ЦБО')
    child_ids = fields.One2many('budget.responsibility.center', 'parent_id', 'Дочірні ЦБО')

    responsible_user_id = fields.Many2one('res.users', 'Відповідальний')
    department_id = fields.Many2one('hr.department', 'Підрозділ')
    company_id = fields.Many2one('res.company', 'Підприємство', required=True, default=lambda self: self.env.company)

    sequence = fields.Integer('Послідовність', default=10)
    active = fields.Boolean('Активний', default=True)

    budget_type_ids = fields.Many2many(
        'budget.type',
        'cbo_budget_type_rel',
        'cbo_id',
        'budget_type_id',
        'Типи бюджетів'
    )

    @api.constrains('parent_id')
    def _check_hierarchy(self):
        for record in self:
            if record.parent_id and self._check_recursion():
                raise ValidationError('Неможливо створити рекурсивну ієрархію ЦБО!')


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
    ], 'Категорія бюджету', required=True)

    calculation_method = fields.Selection([
        ('manual', 'Ручне планування'),
        ('norm_based', 'На основі нормативів'),
        ('statistical', 'Статистичний метод'),
        ('contract_based', 'На основі договорів')
    ], 'Метод розрахунку', default='manual')

    responsible_cbo_ids = fields.Many2many(
        'budget.responsibility.center',
        'cbo_budget_type_rel',
        'budget_type_id',
        'cbo_id',
        'Відповідальні ЦБО'
    )

    approval_required = fields.Boolean('Потребує затвердження', default=True)
    sequence = fields.Integer('Послідовність', default=10)
    active = fields.Boolean('Активний', default=True)


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
        ('year', 'Рік')
    ], 'Тип періоду', required=True, default='month')

    state = fields.Selection([
        ('draft', 'Чернетка'),
        ('planning', 'Планування'),
        ('approved', 'Затверджений'),
        ('closed', 'Закритий')
    ], 'Статус', default='draft', required=True)

    company_id = fields.Many2one('res.company', 'Підприємство', required=True, default=lambda self: self.env.company)
    active = fields.Boolean('Активний', default=True)

    @api.constrains('date_start', 'date_end')
    def _check_dates(self):
        for record in self:
            if record.date_start >= record.date_end:
                raise ValidationError('Дата початку має бути менше дати закінчення!')