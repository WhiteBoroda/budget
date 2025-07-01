# -*- coding: utf-8 -*-
# models/budget_category_enhanced.py

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
import logging

_logger = logging.getLogger(__name__)


class BudgetCategoryEnhanced(models.Model):
    """Покращена модель категорій бюджетних витрат"""
    _inherit = 'budget.category'

    # Додаткові поля для аналітики
    budget_line_count = fields.Integer('Кількість позицій бюджету',
                                       compute='_compute_budget_statistics')
    total_planned_amount = fields.Monetary('Загальна планова сума',
                                           compute='_compute_budget_statistics')
    total_actual_amount = fields.Monetary('Загальна фактична сума',
                                          compute='_compute_budget_statistics')
    currency_id = fields.Many2one('res.currency', 'Валюта',
                                  default=lambda self: self.env.company.currency_id)

    # Статистика використання
    usage_frequency = fields.Integer('Частота використання',
                                     compute='_compute_usage_statistics')
    last_used_date = fields.Date('Остання дата використання',
                                 compute='_compute_usage_statistics')

    # Налаштування автоматизації
    auto_account_assignment = fields.Boolean('Автопризначення рахунків', default=True,
                                             help="Автоматично призначати рахунки при створенні позицій")
    default_calculation_method = fields.Selection([
        ('manual', 'Ручний розрахунок'),
        ('formula', 'За формулою'),
        ('percentage', 'Відсоток від базової суми'),
        ('quantity_price', 'Кількість × Ціна')
    ], 'Метод розрахунку за замовчуванням', default='manual')

    # Шаблони для швидкого введення
    template_description = fields.Char('Шаблон опису',
                                       help="Шаблон опису для нових позицій бюджету")
    template_calculation_basis = fields.Text('Шаблон обґрунтування',
                                             help="Шаблон обґрунтування розрахунку")

    # Обмеження та контроль
    min_amount = fields.Monetary('Мінімальна сума', help="Мінімальна сума для позицій цієї категорії")
    max_amount = fields.Monetary('Максимальна сума', help="Максимальна сума для позицій цієї категорії")
    require_justification = fields.Boolean('Обов\'язкове обґрунтування',
                                           help="Вимагати обґрунтування для позицій цієї категорії")

    # Теги для класифікації
    tag_ids = fields.Many2many('budget.category.tag', string='Теги')

    @api.depends('account_mapping_ids.category_id')
    def _compute_budget_statistics(self):
        """Розрахунок статистики по бюджетах"""
        for category in self:
            # Пошук всіх позицій бюджету з цією категорією
            budget_lines = self.env['budget.plan.line'].search([
                ('budget_category_id', '=', category.id)
            ])

            category.budget_line_count = len(budget_lines)
            category.total_planned_amount = sum(budget_lines.mapped('planned_amount'))
            category.total_actual_amount = sum(budget_lines.mapped('actual_amount'))

    @api.depends('account_mapping_ids.category_id')
    def _compute_usage_statistics(self):
        """Розрахунок статистики використання"""
        for category in self:
            budget_lines = self.env['budget.plan.line'].search([
                ('budget_category_id', '=', category.id)
            ], order='create_date desc', limit=1)

            category.usage_frequency = self.env['budget.plan.line'].search_count([
                ('budget_category_id', '=', category.id)
            ])
            category.last_used_date = budget_lines.create_date.date() if budget_lines else False

    @api.constrains('code')
    def _check_code_format(self):
        """Перевірка формату коду категорії"""
        for category in self:
            if category.code:
                import re
                # Код має бути у форматі X.XXX. або X.XXX.X
                pattern = r'^\d+\.\d+\.(\d+)?$'
                if not re.match(pattern, category.code):
                    raise ValidationError(
                        _('Код категорії має бути у форматі X.XXX. або X.XXX.X (наприклад: 1.100. або 2.300.1)')
                    )

    @api.constrains('min_amount', 'max_amount')
    def _check_amount_limits(self):
        """Перевірка лімітів сум"""
        for category in self:
            if category.min_amount and category.max_amount:
                if category.min_amount > category.max_amount:
                    raise ValidationError(
                        _('Мінімальна сума не може бути більше максимальної суми')
                    )

    def action_view_budget_lines(self):
        """Перегляд позицій бюджету з цією категорією"""
        return {
            'type': 'ir.actions.act_window',
            'name': f'Позиції бюджету - {self.name}',
            'res_model': 'budget.plan.line',
            'view_mode': 'tree,form',
            'domain': [('budget_category_id', '=', self.id)],
            'context': {
                'default_budget_category_id': self.id,
                'search_default_group_plan': 1
            }
        }

    def action_map_accounts(self):
        """Дія для налаштування зопоставлення рахунків"""
        return {
            'type': 'ir.actions.act_window',
            'name': f'Зопоставлення рахунків - {self.name}',
            'res_model': 'budget.category.account.mapping',
            'view_mode': 'tree,form',
            'domain': [('category_id', '=', self.id)],
            'context': {'default_category_id': self.id}
        }

    def action_usage_analysis(self):
        """Аналіз використання категорії"""
        return {
            'type': 'ir.actions.act_window',
            'name': f'Аналіз використання - {self.name}',
            'res_model': 'budget.plan.line',
            'view_mode': 'graph,pivot,tree',
            'domain': [('budget_category_id', '=', self.id)],
            'context': {
                'search_default_group_period': 1,
                'search_default_group_cbo': 1
            }
        }

    def action_create_budget_line_template(self):
        """Створення шаблону позиції бюджету"""
        return {
            'type': 'ir.actions.act_window',
            'name': f'Створити позицію - {self.name}',
            'res_model': 'budget.plan.line',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_budget_category_id': self.id,
                'default_description': self.template_description or self.name,
                'default_calculation_basis': self.template_calculation_basis,
                'default_calculation_method': self.default_calculation_method,
                'default_account_id': self.default_account_id.id if self.default_account_id else False
            }
        }

    def get_default_account(self, cbo_id=None, cost_center_id=None):
        """Отримання рахунку за замовчуванням з урахуванням маппінгу"""
        # Пошук найбільш специфічного маппінгу
        domain = [('category_id', '=', self.id), ('active', '=', True)]

        if cost_center_id:
            domain.append(('cost_center_id', '=', cost_center_id))

        mappings = self.account_mapping_ids.filtered(lambda m: m.active).sorted('priority')

        if mappings:
            return mappings[0].account_id

        return self.default_account_id

    @api.model
    def search_by_keywords(self, keywords):
        """Пошук категорій за ключовими словами"""
        if not keywords:
            return self.browse()

        keywords = keywords.lower().strip()
        domain = [
            '|', '|', '|',
            ('name', 'ilike', keywords),
            ('code', 'ilike', keywords),
            ('description', 'ilike', keywords),
            ('tag_ids.name', 'ilike', keywords)
        ]

        return self.search(domain)

    def suggest_code(self, parent_category=None):
        """Пропозиція коду для нової категорії"""
        if parent_category:
            # Підкатегорія
            base_code = parent_category.code.rstrip('.')
            existing_subcategories = self.search([
                ('parent_id', '=', parent_category.id),
                ('code', '=like', f'{base_code}.%')
            ])

            max_subcode = 0
            for subcat in existing_subcategories:
                try:
                    subcode = int(subcat.code.split('.')[-1])
                    max_subcode = max(max_subcode, subcode)
                except:
                    continue

            return f"{base_code}.{max_subcode + 1}"
        else:
            # Основна категорія
            existing_main = self.search([
                ('parent_id', '=', False),
                ('code', '=like', '%.000.')
            ])

            max_main = 0
            for main in existing_main:
                try:
                    main_code = int(main.code.split('.')[0])
                    max_main = max(max_main, main_code)
                except:
                    continue

            return f"{max_main + 1}.000."

    @api.model
    def import_from_excel_data(self, excel_data):
        """Імпорт категорій з даних Excel"""
        created_categories = []
        errors = []

        # Сортування по кодах для правильного порядку створення
        sorted_data = sorted(excel_data, key=lambda x: x.get('code', ''))

        for data in sorted_data:
            try:
                code = data.get('code', '').strip()
                name = data.get('name', '').strip()

                if not code or not name:
                    continue

                # Перевірка існування
                existing = self.search([('code', '=', code)])
                if existing:
                    continue

                # Визначення батьківської категорії
                parent_id = False
                parts = code.split('.')
                if len(parts) > 2 and parts[2]:
                    parent_code = f"{parts[0]}.{parts[1]}."
                    parent = self.search([('code', '=', parent_code)], limit=1)
                    if parent:
                        parent_id = parent.id

                # Створення категорії
                category_vals = {
                    'code': code,
                    'name': name,
                    'description': data.get('description', ''),
                    'parent_id': parent_id,
                    'sequence': int(parts[0]) * 100 if parts else 10,
                    'active': True
                }

                category = self.create(category_vals)
                created_categories.append(category)

            except Exception as e:
                errors.append(f"Помилка для {data.get('code', 'N/A')}: {str(e)}")

        return created_categories, errors


class BudgetCategoryTag(models.Model):
    """Теги для категорій бюджету"""
    _name = 'budget.category.tag'
    _description = 'Тег категорії бюджету'

    name = fields.Char('Назва тегу', required=True)
    color = fields.Integer('Колір')
    description = fields.Text('Опис')


class BudgetCategoryAccountMappingEnhanced(models.Model):
    """Покращене зопоставлення категорій з рахунками"""
    _inherit = 'budget.category.account.mapping'

    # Додаткові умови для маппінгу
    cbo_id = fields.Many2one('budget.responsibility.center', 'ЦБО')
    budget_type_id = fields.Many2one('budget.type', 'Тип бюджету')
    amount_from = fields.Monetary('Сума від')
    amount_to = fields.Monetary('Сума до')
    currency_id = fields.Many2one('res.currency', related='category_id.currency_id')

    # Налаштування автоматизації
    auto_assign = fields.Boolean('Автопризначення', default=True)
    require_approval = fields.Boolean('Потребує підтвердження')

    def get_best_mapping(self, amount=None, cbo_id=None, budget_type_id=None):
        """Пошук найкращого маппінгу за умовами"""
        domain = [('category_id', '=', self.category_id.id), ('active', '=', True)]

        if cbo_id:
            domain.append(('cbo_id', 'in', [False, cbo_id]))
        if budget_type_id:
            domain.append(('budget_type_id', 'in', [False, budget_type_id]))
        if amount:
            domain.extend([
                '|', ('amount_from', '=', False), ('amount_from', '<=', amount),
                '|', ('amount_to', '=', False), ('amount_to', '>=', amount)
            ])

        mappings = self.search(domain, order='priority, id')
        return mappings[0] if mappings else None