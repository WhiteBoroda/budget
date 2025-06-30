# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import UserError


class BudgetAssignCategoriesWizard(models.TransientModel):
    """Мастер массового назначения категорий для позиций бюджета"""
    _name = 'budget.assign.categories.wizard'
    _description = 'Массовое назначение категорий бюджета'

    line_ids = fields.Many2many('budget.plan.line', string='Позиции бюджета')
    line_count = fields.Integer('Количество позиций', compute='_compute_line_count')

    budget_category_id = fields.Many2one('budget.category', 'Категория расходов', required=True)
    cost_center_id = fields.Many2one('budget.cost.center', 'Центр затрат')

    update_accounts = fields.Boolean('Обновить счета', default=True,
                                     help="Автоматически обновить счета согласно новым категориям")

    @api.depends('line_ids')
    def _compute_line_count(self):
        for wizard in self:
            wizard.line_count = len(wizard.line_ids)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)

        # Получаем выбранные записи из контекста
        if self.env.context.get('active_model') == 'budget.plan.line':
            line_ids = self.env.context.get('active_ids', [])
            res['line_ids'] = [(6, 0, line_ids)]

        return res

    def action_assign_categories(self):
        """Выполнение массового назначения категорий"""
        if not self.line_ids:
            raise UserError('Не выбраны позиции для обновления!')

        if not self.budget_category_id:
            raise UserError('Выберите категорию расходов!')

        updated_count = 0

        # Обновляем каждую позицию
        for line in self.line_ids:
            # Проверяем права на редактирование
            if not line.is_editable:
                continue

            # Обновляем категорию и центр затрат
            update_vals = {
                'budget_category_id': self.budget_category_id.id,
            }

            if self.cost_center_id:
                update_vals['cost_center_id'] = self.cost_center_id.id

            line.write(update_vals)

            # Обновляем счета, если нужно
            if self.update_accounts:
                line._compute_accounting_data()

            updated_count += 1

        # Показываем результат
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Обновление завершено!',
                'message': f'Категории назначены для {updated_count} позиций из {len(self.line_ids)}',
                'type': 'success',
                'sticky': False,
            }
        }


class BudgetPlanLineInherit(models.Model):
    """Добавляем computed поле для определения возможности редактирования"""
    _inherit = 'budget.plan.line'

    @api.depends('plan_id.state')
    def _compute_is_editable(self):
        """Определяет можно ли редактировать строку"""
        for line in self:
            line.is_editable = line.plan_id.state in ['draft', 'planning', 'revision']

    is_editable = fields.Boolean('Можна редагувати', compute='_compute_is_editable')