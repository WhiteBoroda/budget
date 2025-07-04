# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class BudgetPlan(models.Model):
    _inherit = 'budget.plan'

    # Додаємо поля для консолідації
    consolidation_level = fields.Selection([
        ('site', 'Площадка'),
        ('company', 'Компанія'),
        ('holding', 'Холдинг')
    ], 'Рівень консолідації', compute='_compute_consolidation_level', store=True)

    is_consolidated = fields.Boolean('Консолідований бюджет', default=False)
    parent_budget_id = fields.Many2one('budget.plan', 'Батьківський бюджет')
    child_budget_ids = fields.One2many('budget.plan', 'parent_budget_id', 'Дочірні бюджети')

    auto_consolidate = fields.Boolean('Автоматична консолідація', default=True,
                                      help="Автоматично оновлювати батьківські бюджети при змінах")

    @api.depends('cbo_id', 'cbo_id.cbo_type', 'cbo_id.parent_id')
    def _compute_consolidation_level(self):
        """Визначення рівня консолідації на основі типу ЦБО"""
        for budget in self:
            if not budget.cbo_id:
                budget.consolidation_level = 'site'
                continue

            cbo_type = budget.cbo_id.cbo_type
            if cbo_type in ['holding']:
                budget.consolidation_level = 'holding'
            elif cbo_type in ['cluster', 'business_direction', 'brand', 'enterprise']:
                budget.consolidation_level = 'company'
            else:
                budget.consolidation_level = 'site'

    @api.model
    def create_consolidation_structure(self, period_id, budget_type_id):
        """Створення структури консолідованих бюджетів для періоду"""

        # 1. Знаходимо всі ЦБО і групуємо по рівнях
        cbo_obj = self.env['budget.responsibility.center']

        # Холдинг рівень
        holding_cbos = cbo_obj.search([('cbo_type', '=', 'holding')])
        # Компанії рівень
        company_cbos = cbo_obj.search([('cbo_type', 'in', ['enterprise', 'business_direction'])])
        # Площадки рівень
        site_cbos = cbo_obj.search([('cbo_type', 'in', ['department', 'division', 'office'])])

        created_budgets = {}

        # 2. Створюємо бюджети для площадок (базовий рівень)
        for cbo in site_cbos:
            budget = self.create({
                'name': f"Бюджет {cbo.name} - {period_id.name}",
                'period_id': period_id,
                'budget_type_id': budget_type_id,
                'cbo_id': cbo.id,
                'consolidation_level': 'site',
                'is_consolidated': False,
                'auto_consolidate': True,
                'state': 'draft'
            })
            created_budgets[cbo.id] = budget

        # 3. Створюємо консолідовані бюджети для компаній
        for cbo in company_cbos:
            # Знаходимо дочірні ЦБО
            child_cbos = cbo_obj.search([('parent_id', '=', cbo.id)])
            child_budgets = [created_budgets.get(child.id) for child in child_cbos if child.id in created_budgets]

            budget = self.create({
                'name': f"Консолідований бюджет {cbo.name} - {period_id.name}",
                'period_id': period_id,
                'budget_type_id': budget_type_id,
                'cbo_id': cbo.id,
                'consolidation_level': 'company',
                'is_consolidated': True,
                'auto_consolidate': True,
                'state': 'draft'
            })

            # Прив'язуємо дочірні бюджети
            for child_budget in child_budgets:
                if child_budget:
                    child_budget.parent_budget_id = budget.id

            created_budgets[cbo.id] = budget

        # 4. Створюємо консолідовані бюджети для холдингу
        for cbo in holding_cbos:
            child_cbos = cbo_obj.search([('parent_id', '=', cbo.id)])
            child_budgets = [created_budgets.get(child.id) for child in child_cbos if child.id in created_budgets]

            budget = self.create({
                'name': f"Консолідований бюджет холдингу {cbo.name} - {period_id.name}",
                'period_id': period_id,
                'budget_type_id': budget_type_id,
                'cbo_id': cbo.id,
                'consolidation_level': 'holding',
                'is_consolidated': True,
                'auto_consolidate': True,
                'state': 'draft'
            })

            for child_budget in child_budgets:
                if child_budget:
                    child_budget.parent_budget_id = budget.id

            created_budgets[cbo.id] = budget

        return created_budgets

    def action_consolidate_up(self):
        """Консолідація бюджету вгору по ієрархії"""
        self.ensure_one()

        if not self.parent_budget_id:
            raise UserError('Немає батьківського бюджету для консолідації')

        parent = self.parent_budget_id

        # Збираємо всі дочірні бюджети батьківського рівня
        all_children = parent.child_budget_ids

        # Очищуємо консолідовані лінії батьківського бюджету
        parent.line_ids.filtered('is_consolidation').unlink()

        # Групуємо по категоріях і консолідуємо
        consolidated_data = {}

        for child_budget in all_children:
            for line in child_budget.line_ids.filtered(lambda l: not l.is_consolidation):
                key = (line.budget_category_id.id, line.cost_center_id.id)

                if key not in consolidated_data:
                    consolidated_data[key] = {
                        'budget_category_id': line.budget_category_id.id,
                        'cost_center_id': line.cost_center_id.id,
                        'description': f"Консолідація: {line.budget_category_id.name}",
                        'planned_amount': 0,
                        'committed_amount': 0,
                        'actual_amount': 0,
                        'is_consolidation': True,
                    }

                consolidated_data[key]['planned_amount'] += line.planned_amount
                consolidated_data[key]['committed_amount'] += line.committed_amount
                consolidated_data[key]['actual_amount'] += line.actual_amount

        # Створюємо консолідовані лінії
        for data in consolidated_data.values():
            data['plan_id'] = parent.id
            self.env['budget.plan.line'].create(data)

        parent.message_post(
            body=f"Консолідацію оновлено з {len(all_children)} дочірніх бюджетів",
            subject="Автоматична консолідація"
        )

        return True

    def write(self, vals):
        """Автоматична консолідація при змінах"""
        result = super().write(vals)

        # Якщо змінюються лінії бюджету і увімкнена автоконсолідація
        if 'line_ids' in vals and self.auto_consolidate and self.parent_budget_id:
            # Запускаємо консолідацію з невеликою затримкою
            self.with_delay(eta=30).action_consolidate_up()

        return result

    def action_view_consolidated_structure(self):
        """Перегляд всієї структури консолідації"""
        self.ensure_one()

        # Знаходимо корневий бюджет
        root_budget = self
        while root_budget.parent_budget_id:
            root_budget = root_budget.parent_budget_id

        # Збираємо всю ієрархію
        all_budgets = [root_budget.id]

        def collect_children(budget):
            for child in budget.child_budget_ids:
                all_budgets.append(child.id)
                collect_children(child)

        collect_children(root_budget)

        return {
            'type': 'ir.actions.act_window',
            'name': 'Структура консолідації',
            'res_model': 'budget.plan',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', all_budgets)],
            'context': {
                'group_by': ['consolidation_level', 'cbo_id'],
                'expand': True
            }
        }

    def action_copy_from_previous_period(self):
        """Копіювання з попереднього періоду"""
        return {
            'type': 'ir.actions.act_window',
            'name': 'Копіювання з попереднього періоду',
            'res_model': 'budget.copy.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_target_budget_id': self.id,
                'default_period_id': self.period_id.id,
                'default_cbo_id': self.cbo_id.id,
                'default_budget_type_id': self.budget_type_id.id
            }
        }


class BudgetPlanLine(models.Model):
    _inherit = 'budget.plan.line'

    is_consolidation = fields.Boolean('Консолідована лінія', default=False,
                                      help="Лінія створена автоматично через консолідацію")
    source_budget_ids = fields.Many2many('budget.plan', string='Джерела консолідації',
                                         help="Бюджети, з яких консолідована ця лінія")