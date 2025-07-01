# -*- coding: utf-8 -*-
# models/budget_category_enhanced.py

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
import logging, re

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
        """Перевірка формату коду категорії з розширенням до X.XXX.X.X"""
        for category in self:
            if category.code:
                # Дозволяємо різні формати для гнучкості:
                patterns = [
                    r'^\d+\.\d{3}\.\d+\.\d+$',  # X.XXX.X.X (новий розширений формат)
                    r'^\d+\.\d{3}\.\d+$',  # X.XXX.X (середній формат)
                    r'^\d+\.\d{3}\.$',  # X.XXX. (старий формат з крапкою)
                    r'^\d+\.\d{3}$',  # X.XXX (без крапки)
                    r'^[A-Z][A-Z0-9_]*$',  # Літерні коди (SALARY, IT_HW тощо)
                ]

                if not any(re.match(pattern, category.code) for pattern in patterns):
                    raise ValidationError(
                        _('Код категорії має бути у одному з форматів:\n'
                          '• X.XXX.X.X (наприклад: 1.100.2.3) - новий розширений формат\n'
                          '• X.XXX.X (наприклад: 2.300.1) - середній формат\n'
                          '• X.XXX. або X.XXX (наприклад: 1.100. або 1.100) - базовий формат\n'
                          '• Літерний код (наприклад: SALARY, IT_HARDWARE) - для системних категорій\n'
                          '\nВведений код: "{}" не відповідає жодному формату').format(category.code)
                    )

    def get_code_level(self):
        """Визначає рівень деталізації коду категорії"""
        if not self.code:
            return 0

        # Перевіряємо різні формати
        if re.match(r'^\d+\.\d{3}\.\d+\.\d+$', self.code):
            return 4  # X.XXX.X.X - найвищий рівень деталізації
        elif re.match(r'^\d+\.\d{3}\.\d+$', self.code):
            return 3  # X.XXX.X - середній рівень
        elif re.match(r'^\d+\.\d{3}\.?$', self.code):
            return 2  # X.XXX. або X.XXX - базовий рівень
        elif re.match(r'^[A-Z][A-Z0-9_]*$', self.code):
            return 1  # Літерний код - системний рівень
        else:
            return 0  # Невідомий формат

    @api.model
    def create_structured_code(self, major=1, group=100, category=1, subcategory=0):
        """
        Створює структурований код у форматі X.XXX.X.X

        :param major: Основна група (1-9)
        :param group: Група в межах основної (000-999)
        :param category: Категорія в межах групи (0-9)
        :param subcategory: Підкатегорія (0-9)
        :return: Код у форматі X.XXX.X.X
        """
        # Валідація параметрів
        if not (1 <= major <= 9):
            raise ValidationError(_('Основна група має бути від 1 до 9'))
        if not (0 <= group <= 999):
            raise ValidationError(_('Група має бути від 000 до 999'))
        if not (0 <= category <= 9):
            raise ValidationError(_('Категорія має бути від 0 до 9'))
        if not (0 <= subcategory <= 9):
            raise ValidationError(_('Підкатегорія має бути від 0 до 9'))

        return f"{major}.{group:03d}.{category}.{subcategory}"

    def upgrade_code_format(self):
        """
        Автоматичне оновлення коду до нового формату X.XXX.X.X
        """
        if not self.code:
            return

        current_level = self.get_code_level()

        if current_level == 4:
            # Вже у правильному форматі
            return
        elif current_level == 3:
            # X.XXX.X -> X.XXX.X.0
            self.code = self.code + ".0"
        elif current_level == 2:
            # X.XXX. -> X.XXX.0.0 або X.XXX -> X.XXX.0.0
            base_code = self.code.rstrip('.')
            self.code = base_code + ".0.0"
        elif current_level == 1:
            # Літерний код залишаємо без змін
            pass

    @api.model
    def batch_upgrade_codes(self):
        """
        Пакетне оновлення всіх кодів категорій до нового формату
        """
        categories = self.search([])
        updated_count = 0

        for category in categories:
            old_code = category.code
            category.upgrade_code_format()
            if old_code != category.code:
                updated_count += 1

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Оновлення завершено',
                'message': f'Оновлено {updated_count} кодів категорій до формату X.XXX.X.X',
                'type': 'success',
            }
        }

    def validate_code_hierarchy(self):
        """
        Перевірка ієрархії кодів (батьківський код має бути менш деталізованим)
        """
        if self.parent_id and self.parent_id.code and self.code:
            parent_level = self.parent_id.get_code_level()
            current_level = self.get_code_level()

            # Батьківський код має бути менш деталізованим або на тому ж рівні
            if parent_level > current_level and current_level > 1:
                raise ValidationError(
                    _('Батьківська категорія "{}" має більш деталізований код ніж дочірня "{}".\n'
                      'Ієрархія кодів має йти від загального до конкретного.').format(
                        self.parent_id.code, self.code
                    )
                )

    @api.constrains('parent_id', 'code')
    def _check_code_hierarchy(self):
        """Перевірка ієрархії при збереженні"""
        for category in self:
            category.validate_code_hierarchy()

    def get_code_description(self):
        """Повертає опис формату коду"""
        level = self.get_code_level()
        descriptions = {
            4: "Повний код (X.XXX.X.X) - найвища деталізація",
            3: "Розширений код (X.XXX.X) - середня деталізація",
            2: "Базовий код (X.XXX) - основна категорія",
            1: "Системний код (літерний) - службова категорія",
            0: "Невідомий формат коду"
        }
        return descriptions.get(level, "Невідомий формат")

    @api.depends('code')
    def _compute_code_info(self):
        """Обчислює інформацію про код"""
        for category in self:
            category.code_level = category.get_code_level()
            category.code_description = category.get_code_description()

    # Додаткові поля для відображення інформації про код
    code_level = fields.Integer('Рівень коду', compute='_compute_code_info', store=True)
    code_description = fields.Char('Опис формату', compute='_compute_code_info', store=True)

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