# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import UserError


class BudgetApprovalWizard(models.TransientModel):
    """Майстер затвердження бюджетів"""
    _name = 'budget.approval.wizard'
    _description = 'Майстер затвердження бюджетів'

    budget_ids = fields.Many2many('budget.plan', string='Бюджети для затвердження')
    approval_type = fields.Selection([
        ('approve', 'Затвердити'),
        ('reject', 'Відхилити'),
        ('revision', 'На доопрацювання')
    ], 'Тип дії', required=True, default='approve')

    comments = fields.Text('Коментарі')

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if self.env.context.get('active_model') == 'budget.plan':
            budget_ids = self.env.context.get('active_ids', [])
            res['budget_ids'] = [(6, 0, budget_ids)]
        return res

    def action_approve(self):
        """Затвердження бюджетів"""
        if not self.budget_ids:
            raise UserError('Оберіть бюджети для затвердження!')

        for budget in self.budget_ids:
            if budget.state != 'coordination':
                raise UserError(f'Бюджет {budget.display_name} не знаходиться в стані узгодження!')

            budget.write({
                'state': 'approved',
                'approved_by_id': self.env.user.id,
                'approval_date': fields.Datetime.now()
            })

            # Додаємо коментар
            if self.comments:
                budget.message_post(
                    body=f"Бюджет затверджено. Коментар: {self.comments}",
                    subject="Затвердження бюджету"
                )

        return {'type': 'ir.actions.act_window_close'}

    def action_reject(self):
        """Відхилення бюджетів"""
        if not self.budget_ids:
            raise UserError('Оберіть бюджети для відхилення!')

        for budget in self.budget_ids:
            budget.write({'state': 'revision'})

            if self.comments:
                budget.message_post(
                    body=f"Бюджет відхилено на доопрацювання. Коментар: {self.comments}",
                    subject="Відхилення бюджету"
                )

        return {'type': 'ir.actions.act_window_close'}