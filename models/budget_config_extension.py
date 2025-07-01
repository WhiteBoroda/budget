# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class BudgetType(models.Model):
    """Розширення існуючого типу бюджету з правильними значеннями budget_category"""
    _inherit = 'budget.type'

    # Видаляємо переоприділення поля budget_category, оскільки воно вже правильно визначене в базовій моделі
    # budget_category вже існує в models/budget_config.py з правильними значеннями

    @api.model
    def _get_default_budget_category_mapping(self):
        """Повертає маппінг кодів на категорії для автоматичного призначення"""
        return {
            'BDR': 'administrative',  # БДР - як адміністративний (узагальнюючий)
            '01': 'direct_costs',  # ФОТ
            '01(2)': 'direct_costs',  # ФОТ додатковий
            '02': 'indirect_costs',  # Розвиток персоналу
            '03': 'indirect_costs',  # Соціальні витрати
            '04': 'administrative',  # Благодійність
            '04(2)': 'administrative',  # Благодійність (маркетинг)
            '05': 'administrative',  # Маркетинг
            '06': 'administrative',  # Податки
            '07': 'administrative',  # Консультації
            '08': 'financial',  # Фінансова діяльність
            '09': 'income',  # Доходи
            '10': 'indirect_costs',  # Оренда
            '11': 'direct_costs',  # Логістика
            '12': 'indirect_costs',  # ІТ
            '13': 'direct_costs',  # Контроль якості
            '14': 'administrative',  # Управління власністю
            '15': 'administrative',  # Юридичні розходи
            '16': 'administrative',  # Охорона праці
            '17': 'administrative',  # Адмін-господарські
            '18': 'indirect_costs',  # Зв'язок та інтернет
            '19': 'direct_costs',  # Енергоносії
            '20': 'indirect_costs',  # Техобслуговування
            '21': 'indirect_costs',  # Ремонт транспорту
            '22': 'direct_costs',  # Експлуатація транспорту
            '23': 'administrative',  # Інші операційні
            '24': 'investment',  # Інвестиції
            '25': 'administrative',  # Безпека
            '26': 'investment',  # Надходження від інвестиційної діяльності
            '27': 'administrative',  # ТОП менеджмент
            '28': 'direct_costs',  # Баланс зерна
            '29': 'direct_costs',  # Розрахунок переробки
            '30': 'direct_costs',  # Баланс муки
            '31': 'administrative',  # Резерв
            '32': 'administrative',  # Професійні послуги холдингу
            'PROD': 'direct_costs',  # Виробничий
            'SALES': 'income',  # Продажі
        }

    @api.model
    def auto_assign_budget_categories(self):
        """Автоматичне призначення категорій для існуючих типів бюджетів"""
        mapping = self._get_default_budget_category_mapping()
        updated_count = 0

        for budget_type in self.search([]):
            if budget_type.code in mapping:
                new_category = mapping[budget_type.code]
                if budget_type.budget_category != new_category:
                    budget_type.budget_category = new_category
                    updated_count += 1

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Категорії оновлено',
                'message': f'Оновлено категорії для {updated_count} типів бюджетів',
                'type': 'success',
            }
        }

    @api.onchange('code')
    def _onchange_code_set_category(self):
        """Автоматичне встановлення категорії при зміні коду"""
        if self.code:
            mapping = self._get_default_budget_category_mapping()
            if self.code in mapping:
                self.budget_category = mapping[self.code]

    def get_category_color(self):
        """Повертає колір для категорії (для UI)"""
        colors = {
            'income': '#28a745',  # Зелений
            'direct_costs': '#dc3545',  # Червоний
            'indirect_costs': '#fd7e14',  # Оранжевий
            'administrative': '#6c757d',  # Сірий
            'financial': '#007bff',  # Синій
            'investment': '#20c997',  # Бірюзовий
        }
        return colors.get(self.budget_category, '#6c757d')

    def get_category_icon(self):
        """Повертає іконку для категорії"""
        icons = {
            'income': 'fa-arrow-up',
            'direct_costs': 'fa-arrow-down',
            'indirect_costs': 'fa-cogs',
            'administrative': 'fa-building',
            'financial': 'fa-university',
            'investment': 'fa-seedling',
        }
        return icons.get(self.budget_category, 'fa-folder')

    @api.depends('budget_category')
    def _compute_category_info(self):
        """Обчислює інформацію про категорію"""
        for budget_type in self:
            budget_type.category_color = budget_type.get_category_color()
            budget_type.category_icon = budget_type.get_category_icon()

    # Додаткові поля для UI
    category_color = fields.Char('Колір категорії', compute='_compute_category_info')
    category_icon = fields.Char('Іконка категорії', compute='_compute_category_info')