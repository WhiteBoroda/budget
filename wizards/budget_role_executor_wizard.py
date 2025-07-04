from odoo import models, fields, api, _

class BudgetRoleExecutorWizard(models.TransientModel):
    """Майстер для перегляду та керування виконавцями ролей бюджету"""
    _name = 'budget.role.executor.wizard'
    _description = 'Майстер виконавців ролей бюджету'

    budget_plan_id = fields.Many2one('budget.plan', 'Бюджетний план', required=True)

    # Поточні виконавці
    current_creator_ids = fields.Many2many(
        'res.users',
        relation='budget_role_wizard_creator_rel',
        string='Поточні складачі',
        related='budget_plan_id.current_creator_ids'
    )

    current_reviewer_ids = fields.Many2many(
        'res.users',
        relation='budget_role_wizard_reviewer_rel',
        string='Поточні перевіряючі',
        related='budget_plan_id.current_reviewer_ids'
    )

    current_approver_ids = fields.Many2many(
        'res.users',
        relation='budget_role_wizard_approver_rel',
        string='Поточні затверджуючі',
        related='budget_plan_id.current_approver_ids'
    )

    # Історія ролей
    role_history_ids = fields.One2many(
        'budget.role.history.line',
        'wizard_id',
        'Історія призначень',
        compute='_compute_role_history'
    )

    @api.depends('budget_plan_id')
    def _compute_role_history(self):
        """Обчислення історії ролей"""
        for wizard in self:
            history_lines = []
            if wizard.budget_plan_id:
                history = wizard.budget_plan_id.get_role_history()
                for executor in history:
                    history_lines.append((0, 0, {
                        'date': executor.date,
                        'user_id': executor.user_id.id,
                        'role_id': executor.role_id.id,
                        'status_role': executor.status_role,
                        'note': executor.note
                    }))
            wizard.role_history_ids = history_lines


class BudgetRoleHistoryLine(models.TransientModel):
    """Лінії історії ролей для майстра"""
    _name = 'budget.role.history.line'
    _description = 'Історія ролей бюджету'

    wizard_id = fields.Many2one('budget.role.executor.wizard')
    date = fields.Date('Дата')
    user_id = fields.Many2one('res.users', 'Користувач')
    role_id = fields.Many2one('business.role.catalog', 'Роль')
    status_role = fields.Boolean('Активна')
    note = fields.Char('Примітка')