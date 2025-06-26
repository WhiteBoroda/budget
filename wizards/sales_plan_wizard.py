# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import UserError


class SalesPlanWizard(models.TransientModel):
    """Майстер створення плану продажів"""
    _name = 'sales.plan.wizard'
    _description = 'Майстер створення плану продажів'

    period_id = fields.Many2one('budget.period', 'Період', required=True)
    company_id = fields.Many2one('res.company', 'Підприємство', required=True, default=lambda self: self.env.company)
    base_period_id = fields.Many2one('budget.period', 'Базовий період')
    growth_rate = fields.Float('Темп росту, %', default=0.0)
    copy_previous = fields.Boolean('Копіювати з попереднього періоду', default=True)

    product_category_ids = fields.Many2many('product.category', string='Категорії товарів')

    def action_create_plan(self):
        """Створення плану продажів"""
        # Перевіряємо чи не існує вже план для цього періоду та компанії
        existing_plan = self.env['budget.sales.plan'].search([
            ('period_id', '=', self.period_id.id),
            ('company_id', '=', self.company_id.id)
        ])

        if existing_plan:
            raise UserError('План продажів для цього періоду та підприємства вже існує!')

        # Створюємо новий план
        plan_vals = {
            'period_id': self.period_id.id,
            'company_id': self.company_id.id,
            'state': 'draft',
            'responsible_user_id': self.env.user.id
        }

        new_plan = self.env['budget.sales.plan'].create(plan_vals)

        # Якщо потрібно копіювати з попереднього періоду
        if self.copy_previous and self.base_period_id:
            self._copy_from_previous(new_plan)

        return {
            'type': 'ir.actions.act_window',
            'name': 'План продажів',
            'res_model': 'budget.sales.plan',
            'res_id': new_plan.id,
            'view_mode': 'form',
            'target': 'current'
        }

    def _copy_from_previous(self, new_plan):
        """Копіювання даних з попереднього періоду"""
        base_plan = self.env['budget.sales.plan'].search([
            ('period_id', '=', self.base_period_id.id),
            ('company_id', '=', self.company_id.id)
        ], limit=1)

        if base_plan:
            # Встановлюємо продажі попереднього періоду
            new_plan.previous_period_sales = base_plan.total_planned_amount

            # Копіюємо лінії з урахуванням темпу росту
            for line in base_plan.line_ids:
                new_qty = line.planned_qty * (1 + self.growth_rate / 100)
                new_price = line.planned_price * (1 + self.growth_rate / 100)

                self.env['budget.sales.plan.line'].create({
                    'plan_id': new_plan.id,
                    'product_id': line.product_id.id,
                    'product_category_id': line.product_category_id.id,
                    'sales_channel': line.sales_channel,
                    'region': line.region,
                    'planned_qty': new_qty,
                    'planned_price': new_price,
                    'discount_percent': line.discount_percent,
                    'return_percent': line.return_percent,
                    'notes': f"Скопійовано з {self.base_period_id.name} з ростом {self.growth_rate}%"
                })