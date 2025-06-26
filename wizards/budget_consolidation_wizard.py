# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import UserError


class BudgetConsolidationWizard(models.TransientModel):
    """Майстер консолідації бюджетів"""
    _name = 'budget.consolidation.wizard'
    _description = 'Майстер консолідації бюджетів'

    period_id = fields.Many2one('budget.period', 'Період', required=True)
    company_ids = fields.Many2many('res.company', string='Підприємства')
    consolidation_level = fields.Selection([
        ('level2', 'Рівень ПП'),
        ('level1', 'Консолідований рівень')
    ], 'Рівень консолідації', required=True, default='level2')

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        # За замовчуванням обираємо всі компанії
        companies = self.env['res.company'].search([])
        res['company_ids'] = [(6, 0, companies.ids)]
        return res

    def action_consolidate(self):
        """Виконання консолідації"""
        if self.consolidation_level == 'level2':
            return self._consolidate_to_level2()
        else:
            return self._consolidate_to_level1()

    def _consolidate_to_level2(self):
        """Консолідація до рівня ПП"""
        for company in self.company_ids:
            # Знаходимо всі затверджені бюджети 3 рівня для цього підприємства
            level3_budgets = self.env['budget.plan'].search([
                ('period_id', '=', self.period_id.id),
                ('company_id', '=', company.id),
                ('level', '=', 'level3'),
                ('state', '=', 'approved')
            ])

            # Групуємо за типами бюджетів
            budget_types = level3_budgets.mapped('budget_type_id')

            for budget_type in budget_types:
                # Створюємо консолідований бюджет рівня 2
                type_budgets = level3_budgets.filtered(lambda b: b.budget_type_id == budget_type)
                total_amount = sum(type_budgets.mapped('planned_amount'))

                # Знаходимо ЦБО керівництва підприємства
                company_cbo = self.env['budget.responsibility.center'].search([
                    ('level', '=', 'production_enterprise'),
                    ('company_id', '=', company.id),
                    ('code', 'like', '%MGT%')
                ], limit=1)

                if not company_cbo:
                    continue

                # Створюємо або оновлюємо бюджет рівня 2
                level2_budget = self.env['budget.plan'].search([
                    ('period_id', '=', self.period_id.id),
                    ('company_id', '=', company.id),
                    ('budget_type_id', '=', budget_type.id),
                    ('level', '=', 'level2')
                ], limit=1)

                if level2_budget:
                    # Оновлюємо існуючий
                    level2_budget.write({
                        'planned_amount': total_amount,
                        'state': 'approved',
                        'approved_by_id': self.env.user.id,
                        'approval_date': fields.Datetime.now()
                    })
                else:
                    # Створюємо новий
                    level2_budget = self.env['budget.plan'].create({
                        'period_id': self.period_id.id,
                        'cbo_id': company_cbo.id,
                        'budget_type_id': budget_type.id,
                        'level': 'level2',
                        'state': 'approved',
                        'company_id': company.id,
                        'responsible_user_id': self.env.user.id,
                        'approved_by_id': self.env.user.id,
                        'approval_date': fields.Datetime.now(),
                        'submission_deadline': fields.Date.today()
                    })

                # Зв'язуємо дочірні бюджети
                type_budgets.write({'parent_budget_id': level2_budget.id})

        return {
            'type': 'ir.actions.act_window',
            'name': 'Консолідовані бюджети ПП',
            'res_model': 'budget.plan',
            'view_mode': 'tree,form',
            'domain': [
                ('period_id', '=', self.period_id.id),
                ('level', '=', 'level2'),
                ('company_id', 'in', self.company_ids.ids)
            ]
        }

    def _consolidate_to_level1(self):
        """Консолідація до рівня групи компаній"""
        # Аналогічна логіка для консолідації до рівня 1
        # Реалізується залежно від специфічних потреб
        raise UserError('Консолідація до рівня 1 буде реалізована в наступній версії')