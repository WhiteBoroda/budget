# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta


class BudgetCopyWizard(models.TransientModel):
    """Wizard для копіювання бюджетів між періодами"""
    _name = 'budget.copy.wizard'
    _description = 'Майстер копіювання бюджетів'

    # Цільовий бюджет
    target_budget_id = fields.Many2one('budget.plan', 'Цільовий бюджет', required=True)

    # Параметри копіювання
    copy_mode = fields.Selection([
        ('previous_period', 'З попереднього періоду'),
        ('specific_period', 'З конкретного періоду'),
        ('same_period_previous_year', 'З аналогічного періоду минулого року'),
        ('template', 'З шаблону'),
        ('another_budget', 'З іншого бюджету')
    ], 'Режим копіювання', required=True, default='previous_period')

    # Джерело копіювання
    source_period_id = fields.Many2one('budget.period', 'Період-джерело')
    source_budget_id = fields.Many2one('budget.plan', 'Бюджет-джерело')
    template_id = fields.Many2one('budget.template', 'Шаблон')

    # Налаштування копіювання
    copy_amounts = fields.Boolean('Копіювати суми', default=True)
    copy_quantities = fields.Boolean('Копіювати кількості', default=True)
    copy_descriptions = fields.Boolean('Копіювати описи', default=True)
    copy_categories = fields.Boolean('Копіювати категорії', default=True)

    # Коефіцієнти коригування
    amount_adjustment_type = fields.Selection([
        ('none', 'Без змін'),
        ('percentage', 'Процентне коригування'),
        ('fixed_amount', 'Фіксована сума'),
        ('inflation', 'Індексація на інфляцію')
    ], 'Коригування сум', default='none')

    adjustment_value = fields.Float('Значення коригування', default=0.0,
                                    help="Процент (+/-) або фіксована сума")
    inflation_rate = fields.Float('Рівень інфляції (%)', default=5.0)

    # Фільтри копіювання
    filter_by_category = fields.Boolean('Фільтрувати по категоріях')
    category_ids = fields.Many2many('budget.category', string='Категорії для копіювання')

    min_amount = fields.Float('Мінімальна сума')
    max_amount = fields.Float('Максимальна сума')

    # Результати
    preview_mode = fields.Boolean('Режим попереднього перегляду', default=False)
    copy_summary = fields.Text('Результат копіювання', readonly=True)

    @api.onchange('copy_mode', 'target_budget_id')
    def _onchange_copy_mode(self):
        """Автоматичне визначення джерела на основі режиму"""
        if not self.target_budget_id:
            return

        target = self.target_budget_id

        if self.copy_mode == 'previous_period':
            # Попередній період того ж типу та ЦБО
            previous_period = self._find_previous_period(target.period_id)
            if previous_period:
                source_budget = self.env['budget.plan'].search([
                    ('period_id', '=', previous_period.id),
                    ('budget_type_id', '=', target.budget_type_id.id),
                    ('cbo_id', '=', target.cbo_id.id)
                ], limit=1)
                self.source_budget_id = source_budget
                self.source_period_id = previous_period

        elif self.copy_mode == 'same_period_previous_year':
            # Аналогічний період минулого року
            previous_year_period = self._find_same_period_previous_year(target.period_id)
            if previous_year_period:
                source_budget = self.env['budget.plan'].search([
                    ('period_id', '=', previous_year_period.id),
                    ('budget_type_id', '=', target.budget_type_id.id),
                    ('cbo_id', '=', target.cbo_id.id)
                ], limit=1)
                self.source_budget_id = source_budget
                self.source_period_id = previous_year_period

    def _find_previous_period(self, current_period):
        """Знаходження попереднього періоду"""
        return self.env['budget.period'].search([
            ('date_end', '<', current_period.date_start)
        ], order='date_end desc', limit=1)

    def _find_same_period_previous_year(self, current_period):
        """Знаходження аналогічного періоду минулого року"""
        previous_year_start = current_period.date_start - relativedelta(years=1)
        previous_year_end = current_period.date_end - relativedelta(years=1)

        return self.env['budget.period'].search([
            ('date_start', '>=', previous_year_start - timedelta(days=15)),
            ('date_start', '<=', previous_year_start + timedelta(days=15)),
            ('date_end', '>=', previous_year_end - timedelta(days=15)),
            ('date_end', '<=', previous_year_end + timedelta(days=15))
        ], limit=1)

    def action_preview_copy(self):
        """Попередній перегляд копіювання"""
        self.preview_mode = True
        lines_to_copy = self._get_source_lines()

        if not lines_to_copy:
            raise UserError('Не знайдено ліній для копіювання за заданими критеріями')

        # Розрахунок статистики
        total_lines = len(lines_to_copy)
        total_amount = sum(self._calculate_adjusted_amount(line.planned_amount)
                           for line in lines_to_copy)

        categories = lines_to_copy.mapped('budget_category_id.name')
        categories_text = ', '.join(categories[:5])
        if len(categories) > 5:
            categories_text += f' та ще {len(categories) - 5}'

        self.copy_summary = f"""
📋 ПОПЕРЕДНІЙ ПЕРЕГЛЯД КОПІЮВАННЯ

🔢 Загальна статистика:
• Ліній для копіювання: {total_lines}
• Загальна сума після коригування: {total_amount:,.2f} тыс.грн
• Категорії: {categories_text}

⚙️ Налаштування:
• Режим: {dict(self._fields['copy_mode'].selection)[self.copy_mode]}
• Коригування сум: {dict(self._fields['amount_adjustment_type'].selection)[self.amount_adjustment_type]}
{f'• Значення коригування: {self.adjustment_value}%' if self.amount_adjustment_type == 'percentage' else ''}

🎯 Цільовий бюджет: {self.target_budget_id.name}
📅 Період: {self.target_budget_id.period_id.name}
🏢 ЦБО: {self.target_budget_id.cbo_id.name}
        """

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'budget.copy.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'context': {'preview_done': True}
        }

    def action_execute_copy(self):
        """Виконання копіювання"""
        if not self.target_budget_id:
            raise UserError('Не вказано цільовий бюджет')

        lines_to_copy = self._get_source_lines()

        if not lines_to_copy:
            raise UserError('Не знайдено ліній для копіювання')

        # Очищуємо існуючі лінії цільового бюджету (опційно)
        if self.env.context.get('clear_existing'):
            self.target_budget_id.line_ids.unlink()

        copied_lines = 0
        total_amount = 0

        for source_line in lines_to_copy:
            new_amount = self._calculate_adjusted_amount(source_line.planned_amount)

            line_vals = {
                'plan_id': self.target_budget_id.id,
                'planned_amount': new_amount,
            }

            # Копіюємо поля згідно з налаштуваннями
            if self.copy_descriptions:
                line_vals['description'] = source_line.description
            if self.copy_categories:
                line_vals['budget_category_id'] = source_line.budget_category_id.id
                line_vals['cost_center_id'] = source_line.cost_center_id.id
            if self.copy_quantities:
                line_vals['quantity'] = source_line.quantity
                line_vals['unit_price'] = self._calculate_adjusted_amount(source_line.unit_price)

            # Додаткові поля
            line_vals.update({
                'account_id': source_line.account_id.id if source_line.account_id else False,
                'analytic_account_id': source_line.analytic_account_id.id if source_line.analytic_account_id else False,
                'calculation_method': source_line.calculation_method,
            })

            self.env['budget.plan.line'].create(line_vals)
            copied_lines += 1
            total_amount += new_amount

        # Додаємо коментар до бюджету
        copy_info = f"Скопійовано {copied_lines} ліній"
        if self.source_budget_id:
            copy_info += f" з бюджету {self.source_budget_id.name}"
        elif self.template_id:
            copy_info += f" з шаблону {self.template_id.name}"

        self.target_budget_id.message_post(
            body=copy_info,
            subject="Копіювання бюджетних ліній"
        )

        # Результат
        self.copy_summary = f"""
✅ КОПІЮВАННЯ ЗАВЕРШЕНО УСПІШНО!

📊 Результати:
• Скопійовано ліній: {copied_lines}
• Загальна сума: {total_amount:,.2f} тыс.грн
• Цільовий бюджет: {self.target_budget_id.name}

🔄 Наступні кроки:
1. Перевірте скопійовані дані
2. Внесіть необхідні коригування
3. Відправте бюджет на затвердження
        """

        return {
            'type': 'ir.actions.act_window',
            'name': 'Скопійований бюджет',
            'res_model': 'budget.plan',
            'res_id': self.target_budget_id.id,
            'view_mode': 'form',
            'target': 'current'
        }

    def _get_source_lines(self):
        """Отримання ліній джерела для копіювання"""
        lines = self.env['budget.plan.line']

        if self.copy_mode == 'template' and self.template_id:
            # Копіювання з шаблону - створюємо лінії на основі шаблону
            template_lines = self.template_id.line_ids
            return template_lines  # Потрібна окрема обробка для шаблонів
        elif self.source_budget_id:
            lines = self.source_budget_id.line_ids
        else:
            return lines

        # Застосовуємо фільтри
        if self.filter_by_category and self.category_ids:
            lines = lines.filtered(lambda l: l.budget_category_id.id in self.category_ids.ids)

        if self.min_amount > 0:
            lines = lines.filtered(lambda l: l.planned_amount >= self.min_amount)

        if self.max_amount > 0:
            lines = lines.filtered(lambda l: l.planned_amount <= self.max_amount)

        return lines

    def _calculate_adjusted_amount(self, original_amount):
        """Розрахунок скоригованої суми"""
        if not self.copy_amounts or self.amount_adjustment_type == 'none':
            return original_amount

        if self.amount_adjustment_type == 'percentage':
            return original_amount * (1 + self.adjustment_value / 100)
        elif self.amount_adjustment_type == 'fixed_amount':
            return original_amount + self.adjustment_value
        elif self.amount_adjustment_type == 'inflation':
            return original_amount * (1 + self.inflation_rate / 100)

        return original_amount