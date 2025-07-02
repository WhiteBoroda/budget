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
            # ИСПРАВЛЕНО: заменил 'level' на 'budget_level'
            level3_budgets = self.env['budget.plan'].search([
                ('period_id', '=', self.period_id.id),
                ('company_id', '=', company.id),
                ('budget_level', '=', 'functional'),  # функціональний = 3 рівень
                ('state', '=', 'approved')
            ])

            # Групуємо за типами бюджетів
            budget_types = level3_budgets.mapped('budget_type_id')

            for budget_type in budget_types:
                # Створюємо консолідований бюджет рівня 2
                type_budgets = level3_budgets.filtered(lambda b: b.budget_type_id == budget_type)
                total_amount = sum(type_budgets.mapped('planned_amount'))

                # Знаходимо ЦБО керівництва підприємства
                # ИСПРАВЛЕНО: заменил 'level' на 'budget_level'
                company_cbo = self.env['budget.responsibility.center'].search([
                    ('budget_level', '=', 'operational'),  # операційний = рівень підприємства
                    ('company_ids', 'in', [company.id]),  # ИСПРАВЛЕНО: many2many поле
                    ('cbo_type', '=', 'enterprise')
                ], limit=1)

                if not company_cbo:
                    # Створюємо ЦБО підприємства якщо немає
                    company_cbo = self.env['budget.responsibility.center'].create({
                        'name': f'Керівництво {company.name}',
                        'code': f'{company.name[:3].upper()}_MGT',
                        'cbo_type': 'enterprise',
                        'budget_level': 'operational',
                        'company_ids': [(6, 0, [company.id])],
                        'responsible_user_id': self.env.user.id
                    })

                # Створюємо або оновлюємо бюджет рівня 2
                # ИСПРАВЛЕНО: заменил 'level' на 'budget_level'
                level2_budget = self.env['budget.plan'].search([
                    ('period_id', '=', self.period_id.id),
                    ('company_id', '=', company.id),
                    ('budget_type_id', '=', budget_type.id),
                    ('budget_level', '=', 'operational')  # операційний рівень
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
                        'budget_level': 'operational',  # ИСПРАВЛЕНО
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
                ('budget_level', '=', 'operational'),  # ИСПРАВЛЕНО
                ('company_id', 'in', self.company_ids.ids)
            ]
        }

    def _consolidate_to_level1(self):
        """Консолідація до рівня групи компаній"""
        # Знаходимо всі затверджені бюджети рівня 2 (підприємства)
        level2_budgets = self.env['budget.plan'].search([
            ('period_id', '=', self.period_id.id),
            ('company_id', 'in', self.company_ids.ids),
            ('budget_level', '=', 'operational'),  # ИСПРАВЛЕНО
            ('state', '=', 'approved')
        ])

        # Групуємо за типами бюджетів
        budget_types = level2_budgets.mapped('budget_type_id')

        for budget_type in budget_types:
            type_budgets = level2_budgets.filtered(lambda b: b.budget_type_id == budget_type)
            total_amount = sum(type_budgets.mapped('planned_amount'))

            # Знаходимо або створюємо ЦБО групи компаній
            group_cbo = self.env['budget.responsibility.center'].search([
                ('budget_level', '=', 'strategic'),  # стратегічний рівень
                ('cbo_type', '=', 'holding')
            ], limit=1)

            if not group_cbo:
                group_cbo = self.env['budget.responsibility.center'].create({
                    'name': 'Група компаній',
                    'code': 'GROUP',
                    'cbo_type': 'holding',
                    'budget_level': 'strategic',
                    'company_ids': [(6, 0, self.company_ids.ids)],
                    'responsible_user_id': self.env.user.id
                })

            # Створюємо консолідований бюджет рівня 1
            level1_budget = self.env['budget.plan'].search([
                ('period_id', '=', self.period_id.id),
                ('budget_type_id', '=', budget_type.id),
                ('budget_level', '=', 'strategic'),  # ИСПРАВЛЕНО
                ('cbo_id', '=', group_cbo.id)
            ], limit=1)

            if level1_budget:
                level1_budget.write({
                    'planned_amount': total_amount,
                    'state': 'approved',
                    'approved_by_id': self.env.user.id,
                    'approval_date': fields.Datetime.now()
                })
            else:
                level1_budget = self.env['budget.plan'].create({
                    'period_id': self.period_id.id,
                    'cbo_id': group_cbo.id,
                    'budget_type_id': budget_type.id,
                    'budget_level': 'strategic',  # ИСПРАВЛЕНО
                    'state': 'approved',
                    'company_id': self.env.company.id,  # основна компанія
                    'responsible_user_id': self.env.user.id,
                    'approved_by_id': self.env.user.id,
                    'approval_date': fields.Datetime.now(),
                    'submission_deadline': fields.Date.today()
                })

            # Зв'язуємо дочірні бюджети
            type_budgets.write({'parent_budget_id': level1_budget.id})

        return {
            'type': 'ir.actions.act_window',
            'name': 'Консолідовані бюджети групи',
            'res_model': 'budget.plan',
            'view_mode': 'tree,form',
            'domain': [
                ('period_id', '=', self.period_id.id),
                ('budget_level', '=', 'strategic')  # ИСПРАВЛЕНО
            ]
        }