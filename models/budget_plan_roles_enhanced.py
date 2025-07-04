from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from datetime import date, timedelta

class BudgetPlanRolesEnhanced(models.Model):
    """Додаткові методи для роботи з ролями в бюджетуванні"""
    _inherit = 'budget.plan'

    def action_auto_assign_roles(self):
        """Автоматичне призначення ролей на основі налаштувань"""
        mapping_data = self.env['budget.role.mapping'].get_roles_for_budget(self)

        if mapping_data:
            self.write({
                'budget_creator_role_id': mapping_data.get('budget_creator_role_id'),
                'budget_reviewer_role_id': mapping_data.get('budget_reviewer_role_id'),
                'budget_approver_role_id': mapping_data.get('budget_approver_role_id'),
                'use_role_based_approval': True
            })

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'message': 'Ролі успішно призначено автоматично',
                    'type': 'success',
                    'sticky': False,
                }
            }
        else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'message': 'Не знайдено підходящих налаштувань ролей',
                    'type': 'warning',
                    'sticky': False,
                }
            }

    def action_view_role_executors(self):
        """Перегляд поточних виконавців ролей"""
        return {
            'name': f'Виконавці ролей для бюджету {self.display_name}',
            'type': 'ir.actions.act_window',
            'res_model': 'budget.role.executor.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_budget_plan_id': self.id}
        }

    def get_role_history(self, role_type='all'):
        """Отримання історії призначень ролей"""
        if role_type == 'all':
            roles = [self.budget_creator_role_id, self.budget_reviewer_role_id, self.budget_approver_role_id]
        elif role_type == 'creator':
            roles = [self.budget_creator_role_id]
        elif role_type == 'reviewer':
            roles = [self.budget_reviewer_role_id]
        elif role_type == 'approver':
            roles = [self.budget_approver_role_id]
        else:
            return self.env['business.role.executor']

        domain = [('role_id', 'in', [r.id for r in roles if r])]

        if self.cbo_id:
            domain.extend([
                ('res_model_address_1', '=', 'budget.responsibility.center'),
                ('first_addressation_id', '=', self.cbo_id.id)
            ])

        return self.env['business.role.executor'].search(domain, order='date desc')
