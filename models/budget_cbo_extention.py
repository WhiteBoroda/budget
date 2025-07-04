# -*- coding: utf-8 -*-

from odoo import models, fields, api


class ResponsibilityCenterExtended(models.Model):
    """Розширення ЦБО для роботи з деревом - СУМІСНО З ODOO 17"""
    _inherit = 'budget.responsibility.center'

    # Computed поля для статистики дерева
    budget_count = fields.Integer('Кількість бюджетів', compute='_compute_budget_stats', store=False)
    child_count = fields.Integer('Кількість дочірніх ЦБО', compute='_compute_child_count', store=False)

    # Поля для кастомізації відображення
    tree_icon = fields.Char('Іконка для дерева', compute='_compute_tree_icon', store=False)
    tree_color_class = fields.Char('CSS клас кольору', compute='_compute_tree_color', store=False)

    @api.depends('child_ids')
    def _compute_child_count(self):
        """Підрахунок дочірніх ЦБО"""
        for cbo in self:
            cbo.child_count = len(cbo.child_ids)

    @api.depends('cbo_type')
    def _compute_tree_icon(self):
        """Іконка залежно від типу ЦБО"""
        icons = {
            'holding': 'fa-university',
            'enterprise': 'fa-industry',
            'business_direction': 'fa-building',
            'department': 'fa-building-o',
            'division': 'fa-folder',
            'office': 'fa-briefcase',
            'team': 'fa-users',
            'project': 'fa-tasks'
        }

        for cbo in self:
            cbo.tree_icon = icons.get(cbo.cbo_type, 'fa-folder')

    @api.depends('budget_level')
    def _compute_tree_color(self):
        """CSS клас кольору залежно від рівня бюджетування"""
        colors = {
            'strategic': 'text-primary',
            'tactical': 'text-info',
            'operational': 'text-success',
            'functional': 'text-secondary'
        }

        for cbo in self:
            cbo.tree_color_class = colors.get(cbo.budget_level, 'text-dark')

    def _compute_budget_stats(self):
        """Підрахунок статистики бюджетів"""
        # Використовуємо SQL для продуктивності
        if not self.ids:
            return

        query = """
                SELECT cbo_id, COUNT(*) as budget_count
                FROM budget_plan
                WHERE cbo_id IN %s
                GROUP BY cbo_id \
                """

        self.env.cr.execute(query, (tuple(self.ids),))
        budget_data = dict(self.env.cr.fetchall())

        for cbo in self:
            cbo.budget_count = budget_data.get(cbo.id, 0)

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

    def action_view_tree_structure(self):
        """Відкриття дерева з фокусом на поточному ЦБО"""
        # Знаходимо корневий ЦБО
        root = self
        while root.parent_id:
            root = root.parent_id

        return {
            'type': 'ir.actions.act_window',
            'name': 'Структура організації',
            'res_model': 'budget.responsibility.center',
            'view_mode': 'tree,form',
            'view_id': self.env.ref('budget.view_responsibility_center_hierarchy_tree').id,
            'domain': [('id', 'child_of', root.id)],
            'context': {
                'active_id': self.id,
                'expand_tree': True
            }
        }

    @api.model
    def get_tree_data_json(self):
        """API для JavaScript компонентів"""
        root_cbos = self.search([('parent_id', '=', False)])

        def build_node(cbo):
            return {
                'id': cbo.id,
                'name': cbo.name,
                'code': cbo.code,
                'cbo_type': cbo.cbo_type,
                'budget_level': cbo.budget_level,
                'budget_count': cbo.budget_count,
                'child_count': cbo.child_count,
                'icon': cbo.tree_icon,
                'color_class': cbo.tree_color_class,
                'responsible_user': cbo.responsible_user_id.name if cbo.responsible_user_id else None,
                'children': [build_node(child) for child in cbo.child_ids.sorted('sequence')]
            }

        return [build_node(cbo) for cbo in root_cbos.sorted('sequence')]


class BudgetPlanExtended(models.Model):
    """Розширення бюджетного плану для дерева"""
    _inherit = 'budget.plan'

    def action_view_lines(self):
        """Перегляд ліній бюджету"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Лінії бюджету: {self.display_name}',
            'res_model': 'budget.plan.line',
            'view_mode': 'tree,form',
            'domain': [('plan_id', '=', self.id)],
            'context': {
                'default_plan_id': self.id
            }
        }

    def action_view_cbo_tree(self):
        """Перегляд в дереві ЦБО"""
        self.ensure_one()
        return self.cbo_id.action_view_tree_structure()