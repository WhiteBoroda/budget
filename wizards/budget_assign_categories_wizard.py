# -*- coding: utf-8 -*-
# wizards/budget_assign_categories_wizard.py

from odoo import models, fields, api
from odoo.exceptions import UserError


class BudgetAssignCategoriesWizard(models.TransientModel):
    """Майстер для масового призначення категорій бюджетним позиціям"""
    _name = 'budget.assign.categories.wizard'
    _description = 'Майстер призначення категорій'

    # Обрані позиції бюджету
    line_ids = fields.Many2many('budget.plan.line', string='Позиції бюджету')
    line_count = fields.Integer('Кількість позицій', compute='_compute_line_count')

    # Категорії для призначення
    budget_category_id = fields.Many2one('budget.category', 'Категорія бюджету', required=True)
    cost_center_id = fields.Many2one('budget.cost.center', 'Центр витрат')

    # Опція оновлення рахунків
    update_accounts = fields.Boolean('Оновити облікові рахунки', default=True,
                                     help="Автоматично визначити рахунки на основі категорій")

    # Поля для відображення інформації про категорію
    category_code = fields.Char('Код категорії', related='budget_category_id.code', readonly=True)
    category_description = fields.Text('Опис категорії', related='budget_category_id.description', readonly=True)

    @api.depends('line_ids')
    def _compute_line_count(self):
        for wizard in self:
            wizard.line_count = len(wizard.line_ids)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)

        # Отримуємо обрані позиції з контексту
        if self.env.context.get('active_model') == 'budget.plan.line':
            line_ids = self.env.context.get('active_ids', [])
            res['line_ids'] = [(6, 0, line_ids)]

        return res

    def action_assign_categories(self):
        """Призначення категорій обраним позиціям"""
        if not self.line_ids:
            raise UserError('Не обрано жодної позиції бюджету!')

        if not self.budget_category_id:
            raise UserError('Оберіть категорію бюджету!')

        # Перевіряємо чи всі позиції можна редагувати
        non_editable_lines = self.line_ids.filtered(
            lambda l: l.plan_id.state not in ['draft', 'planning', 'revision']
        )

        if non_editable_lines:
            raise UserError(
                f'Деякі позиції не можна редагувати. '
                f'Бюджети мають бути в стані "Чернетка", "Планування" або "Доопрацювання".\n'
                f'Проблемні позиції: {", ".join(non_editable_lines.mapped("display_name"))}'
            )

        # Підготуємо дані для оновлення
        update_values = {
            'budget_category_id': self.budget_category_id.id,
        }

        if self.cost_center_id:
            update_values['cost_center_id'] = self.cost_center_id.id

        # Оновлюємо позиції
        self.line_ids.write(update_values)

        # Якщо потрібно оновити рахунки
        if self.update_accounts:
            for line in self.line_ids:
                line._compute_accounting_data()

        # Додаємо повідомлення до планів
        affected_plans = self.line_ids.mapped('plan_id')
        for plan in affected_plans:
            plan_lines = self.line_ids.filtered(lambda l: l.plan_id == plan)
            plan.message_post(
                body=f"Масово оновлено категорії для {len(plan_lines)} позицій. "
                     f"Категорія: {self.budget_category_id.name}"
            )

        # Повертаємо повідомлення про успіх
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Категорії призначено!',
                'message': f'Успішно оновлено {len(self.line_ids)} позицій бюджету',
                'type': 'success',
                'sticky': False,
            }
        }