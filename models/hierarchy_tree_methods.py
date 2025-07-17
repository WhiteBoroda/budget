# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import UserError


class ResponsibilityCenterTreeMethods(models.Model):
    """Додаткові методи для роботи з деревом ЦБО"""
    _inherit = 'budget.responsibility.center'

    # Додаткові computed поля для дерева
    budget_count = fields.Integer('Кількість бюджетів', compute='_compute_budget_stats')
    child_count = fields.Integer('Кількість дочірніх ЦБО', compute='_compute_child_count')
    total_budget_amount = fields.Monetary('Загальна сума бюджетів', compute='_compute_budget_stats')
    depth_level = fields.Integer('Рівень вкладеності', compute='_compute_depth_level')
    full_path = fields.Char('Повний шлях', compute='_compute_full_path')

    # Поля для відображення в дереві
    display_name_with_icon = fields.Char('Назва з іконкою', compute='_compute_display_name_with_icon')
    tree_summary = fields.Char('Підсумок для дерева', compute='_compute_tree_summary')

    @api.depends('budget_plan_id', 'budget_plan_id.planned_amount')
    def _compute_budget_stats(self):
        """Розрахунок статистики бюджетів для ЦБО"""
        for cbo in self:
            budgets = cbo.budget_plan_id.filtered(lambda b: b.state != 'draft')
            cbo.budget_count = len(budgets)
            cbo.total_budget_amount = sum(budgets.mapped('planned_amount'))

    @api.depends('child_ids')
    def _compute_child_count(self):
        """Підрахунок дочірніх ЦБО"""
        for cbo in self:
            cbo.child_count = len(cbo.child_ids)

    @api.depends('parent_id')
    def _compute_depth_level(self):
        """Розрахунок рівня вкладеності в дереві"""
        for cbo in self:
            level = 0
            current = cbo.parent_id
            while current:
                level += 1
                current = current.parent_id
                # Захист від зациклення
                if level > 10:
                    break
            cbo.depth_level = level

    @api.depends('parent_id', 'name')
    def _compute_full_path(self):
        """Повний шлях від кореня до поточного ЦБО"""
        for cbo in self:
            path_parts = [cbo.name]
            current = cbo.parent_id
            while current:
                path_parts.insert(0, current.name)
                current = current.parent_id
                # Захист від зациклення
                if len(path_parts) > 10:
                    break
            cbo.full_path = ' → '.join(path_parts)

    @api.depends('name', 'cbo_type')
    def _compute_display_name_with_icon(self):
        """Назва з іконкою для відображення в дереві"""
        icons = {
            'holding': '🏛️',
            'enterprise': '🏭',
            'business_direction': '🏢',
            'department': '🏪',
            'division': '📁',
            'office': '🏬',
            'team': '👥',
            'project': '📊'
        }

        for cbo in self:
            icon = icons.get(cbo.cbo_type, '📂')
            cbo.display_name_with_icon = f"{icon} {cbo.name}"

    @api.depends('budget_count', 'child_count', 'responsible_user_id')
    def _compute_tree_summary(self):
        """Підсумок для відображення в дереві"""
        for cbo in self:
            parts = []
            if cbo.budget_count:
                parts.append(f"{cbo.budget_count} 📊")
            if cbo.child_count:
                parts.append(f"{cbo.child_count} 🏢")
            if cbo.responsible_user_id:
                parts.append(f"👤 {cbo.responsible_user_id.name}")

            cbo.tree_summary = ' | '.join(parts) if parts else 'Немає даних'

    def get_tree_data(self, domain=None):
        """Отримання даних для побудови дерева"""
        if domain is None:
            domain = [('active', '=', True)]

        records = self.search(domain)

        tree_data = []
        for record in records:
            tree_data.append({
                'id': record.id,
                'name': record.name,
                'code': record.code,
                'cbo_type': record.cbo_type,
                'budget_level': record.budget_level,
                'parent_id': record.parent_id.id if record.parent_id else None,
                'parent_name': record.parent_id.name if record.parent_id else None,
                'child_ids': record.child_ids.ids,
                'budget_count': record.budget_count,
                'child_count': record.child_count,
                'total_budget_amount': record.total_budget_amount,
                'depth_level': record.depth_level,
                'full_path': record.full_path,
                'responsible_user_id': record.responsible_user_id.id if record.responsible_user_id else None,
                'responsible_user_name': record.responsible_user_id.name if record.responsible_user_id else None,
                'display_name_with_icon': record.display_name_with_icon,
                'tree_summary': record.tree_summary,
                'has_children': bool(record.child_ids),
                'is_leaf': not bool(record.child_ids)
            })

        return tree_data

    def action_view_organization_tree(self):
        """Відкриття дерева організації"""
        return {
            'type': 'ir.actions.act_window',
            'name': 'Структура організації',
            'res_model': 'budget.responsibility.center',
            'view_mode': 'tree,kanban,form',
            'view_id': self.env.ref('budget.view_responsibility_center_hierarchy_tree').id,
            'domain': [('active', '=', True)],
            'context': {
                'group_by': ['parent_id'],
                'expand': True,
                'hierarchy_view': True
            }
        }

    def action_view_budgets(self):
        """Перегляд бюджетів ЦБО"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Бюджети: {self.name}',
            'res_model': 'budget.plan',
            'view_mode': 'tree,form',
            'domain': [('cbo_id', '=', self.id)],
            'context': {
                'default_cbo_id': self.id,
                'search_default_group_period': 1
            }
        }

    def action_create_budget(self):
        """Створення нового бюджету для ЦБО"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Новий бюджет: {self.name}',
            'res_model': 'budget.plan',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_cbo_id': self.id,
                'default_responsible_user_id': self.responsible_user_id.id if self.responsible_user_id else False,
                'default_state': 'draft'
            }
        }

    def action_create_consolidation_structure(self):
        """Створення структури консолідації для ЦБО"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Створення структури консолідації: {self.name}',
            'res_model': 'budget.consolidation.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_root_cbo_id': self.id
            }
        }

    def get_descendants(self, include_self=False):
        """Отримання всіх нащадків ЦБО"""
        descendants = self.env['budget.responsibility.center']

        if include_self:
            descendants |= self

        for child in self.child_ids:
            descendants |= child
            descendants |= child.get_descendants()

        return descendants

    def get_ancestors(self, include_self=False):
        """Отримання всіх предків ЦБО"""
        ancestors = self.env['budget.responsibility.center']

        if include_self:
            ancestors |= self

        if self.parent_id:
            ancestors |= self.parent_id
            ancestors |= self.parent_id.get_ancestors()

        return ancestors


class BudgetPlanTreeMethods(models.Model):
    """Додаткові методи для роботи з деревом бюджетів"""
    _inherit = 'budget.plan'

    # Додаткові поля для дерева
    tree_display_name = fields.Char('Назва для дерева', compute='_compute_tree_display_name')
    consolidation_path = fields.Char('Шлях консолідації', compute='_compute_consolidation_path')
    consolidation_summary = fields.Char('Підсумок консолідації', compute='_compute_consolidation_summary')

    @api.depends('name', 'consolidation_level', 'is_consolidated')
    def _compute_tree_display_name(self):
        """Назва з іконками для дерева"""
        icons = {
            'holding': '🏛️',
            'company': '🏭',
            'site': '🏪'
        }

        for budget in self:
            icon = icons.get(budget.consolidation_level, '💰')
            consolidation_mark = ' (К)' if budget.is_consolidated else ''
            budget.tree_display_name = f"{icon} {budget.name}{consolidation_mark}"

    @api.depends('parent_budget_id', 'name')
    def _compute_consolidation_path(self):
        """Шлях консолідації від кореня"""
        for budget in self:
            path_parts = [budget.name]
            current = budget.parent_budget_id
            while current:
                path_parts.insert(0, current.name)
                current = current.parent_budget_id
                # Захист від зациклення
                if len(path_parts) > 10:
                    break
            budget.consolidation_path = ' → '.join(path_parts)

    @api.depends('child_budget_ids', 'available_amount', 'variance_percent')
    def _compute_consolidation_summary(self):
        """Підсумок для консолідованих бюджетів"""
        for budget in self:
            if budget.is_consolidated and budget.child_budget_ids:
                child_count = len(budget.child_budget_ids)
                avg_execution = sum(
                    budget.child_budget_ids.mapped('variance_percent')) / child_count if child_count else 0
                budget.consolidation_summary = f"{child_count} дочірніх • {avg_execution:.1f}% виконання"
            else:
                budget.consolidation_summary = f"{budget.variance_percent:.1f}% виконання"

    def get_budget_tree_data(self, domain=None):
        """Отримання даних бюджетів для дерева"""
        if domain is None:
            domain = []

        budgets = self.search(domain)

        tree_data = []
        for budget in budgets:
            tree_data.append({
                'id': budget.id,
                'name': budget.name,
                'period_id': budget.period_id.id,
                'period_name': budget.period_id.name,
                'budget_type_id': budget.budget_type_id.id,
                'budget_type_name': budget.budget_type_id.name,
                'cbo_id': budget.cbo_id.id,
                'cbo_name': budget.cbo_id.name,
                'consolidation_level': budget.consolidation_level,
                'is_consolidated': budget.is_consolidated,
                'parent_budget_id': budget.parent_budget_id.id if budget.parent_budget_id else None,
                'child_budget_ids': budget.child_budget_ids.ids,
                'state': budget.state,
                'total_planned_amount': budget.planned_amount,
                'total_actual_amount': budget.actual_amount,
                'execution_percentage': budget.variance_percent,
                'responsible_user_id': budget.responsible_user_id.id if budget.responsible_user_id else None,
                'tree_display_name': budget.tree_display_name,
                'consolidation_path': budget.consolidation_path,
                'consolidation_summary': budget.consolidation_summary,
                'has_children': bool(budget.child_budget_ids),
                'is_leaf': not bool(budget.child_budget_ids)
            })

        return tree_data

    def action_view_consolidation_tree(self):
        """Відкриття дерева консолідації"""
        return {
            'type': 'ir.actions.act_window',
            'name': 'Дерево консолідації бюджетів',
            'res_model': 'budget.plan',
            'view_mode': 'tree,form',
            'view_id': self.env.ref('budget.view_hierarchy_tree_dashboard').id,
            'domain': [('id', 'in', self._get_consolidation_tree_ids())],
            'context': {
                'group_by': ['consolidation_level', 'parent_budget_id'],
                'expand': True,
                'hierarchy_view': True
            }
        }

    def _get_consolidation_tree_ids(self):
        """Отримання ID всього дерева консолідації"""
        self.ensure_one()

        # Знаходимо корневий бюджет
        root = self
        while root.parent_budget_id:
            root = root.parent_budget_id

        # Збираємо всі ID дерева
        tree_ids = [root.id]

        def collect_children(budget):
            for child in budget.child_budget_ids:
                tree_ids.append(child.id)
                collect_children(child)

        collect_children(root)
        return tree_ids

    def action_view_lines(self):
        """Перегляд ліній бюджету"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Лінії бюджету: {self.name}',
            'res_model': 'budget.plan.line',
            'view_mode': 'tree,form',
            'domain': [('plan_id', '=', self.id)],
            'context': {
                'default_plan_id': self.id,
                'search_default_group_category': 1
            }
        }