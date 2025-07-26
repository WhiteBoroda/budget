# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import json


class ResponsibilityCenterExtended(models.Model):
    """Розширення ЦБО для роботи з деревом """
    _inherit = 'budget.responsibility.center'

    # Computed поля для статистики дерева
    budget_count = fields.Integer(
        'Кількість бюджетів',
        compute='_compute_budget_stats',
        store=False,
        help="Кількість активних бюджетів для даного ЦБО"
    )
    child_count = fields.Integer(
        'Кількість дочірніх ЦБО',
        compute='_compute_child_count',
        store=False,
        help="Кількість безпосередніх дочірніх підрозділів"
    )
    descendant_count = fields.Integer(
        'Загальна кількість нащадків',
        compute='_compute_descendant_count',
        store=False,
        help="Загальна кількість всіх підрозділів в ієрархії"
    )

    # Поля для кастомізації відображення
    tree_icon = fields.Char(
        'Іконка для дерева',
        compute='_compute_tree_icon',
        store=False,
        help="CSS клас іконки для відображення в дереві"
    )
    tree_color_class = fields.Char(
        'CSS клас кольору',
        compute='_compute_tree_color',
        store=False,
        help="CSS клас для кольорового кодування в дереві"
    )

    # Поля для статистики та аналітики
    total_budget_amount = fields.Monetary(
        'Загальна сума бюджетів',
        compute='_compute_budget_totals',
        store=False,
        currency_field='company_currency_id',
        help="Сума всіх затверджених бюджетів"
    )
    executed_amount = fields.Monetary(
        'Виконано',
        compute='_compute_budget_totals',
        store=False,
        currency_field='company_currency_id',
        help="Фактично виконана сума бюджетів"
    )
    execution_rate = fields.Float(
        'Рівень виконання, %',
        compute='_compute_budget_totals',
        store=False,
        help="Відсоток виконання бюджетів"
    )

    # Додаткові поля для дерева
    hierarchy_level = fields.Integer(
        'Рівень ієрархії',
        compute='_compute_hierarchy_level',
        store=False,
        help="Глибина вкладеності в дереві (0 - корінь)"
    )
    full_path = fields.Char(
        'Повний шлях',
        compute='_compute_full_path',
        store=False,
        help="Повний шлях в ієрархії через /)"
    )

    # Валютне поле компанії
    company_currency_id = fields.Many2one(
        'res.currency',
        'Валюта компанії',
        compute='_compute_company_currency',
        store=True
    )

    @api.depends('company_ids')
    def _compute_company_currency(self):
        """Обчислення валюти з першої компанії"""
        for cbo in self:
            if cbo.company_ids:
                cbo.company_currency_id = cbo.company_ids[0].currency_id
            else:
                cbo.company_currency_id = self.env.company.currency_id

    @api.depends('child_ids')
    def _compute_child_count(self):
        """Підрахунок дочірніх ЦБО"""
        for cbo in self:
            cbo.child_count = len(cbo.child_ids)

    @api.depends('child_ids', 'child_ids.child_ids')
    def _compute_descendant_count(self):
        """Обчислення загальної кількості нащадків"""
        for cbo in self:
            descendants = self._get_all_descendants(cbo)
            cbo.descendant_count = len(descendants)

    def _get_all_descendants(self, cbo):
        """Рекурсивне отримання всіх нащадків"""
        descendants = []
        for child in cbo.child_ids:
            descendants.append(child.id)
            descendants.extend(self._get_all_descendants(child))
        return descendants

    @api.depends('cbo_type')
    def _compute_tree_icon(self):
        """Обчислення іконки для дерева"""
        icon_map = {
            'holding': 'fa fa-university',
            'cluster': 'fa fa-cubes',
            'business_direction': 'fa fa-compass',
            'brand': 'fa fa-tags',
            'enterprise': 'fa fa-industry',
            'department': 'fa fa-building',
            'division': 'fa fa-sitemap',
            'office': 'fa fa-briefcase',
            'team': 'fa fa-users',
            'project': 'fa fa-project-diagram',
            'other': 'fa fa-folder'
        }

        for cbo in self:
            cbo.tree_icon = icon_map.get(cbo.cbo_type, 'fa fa-folder')

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

    @api.depends('budget_level')
    def _compute_budget_stats(self):
        """Підрахунок статистики бюджетів"""
        for cbo in self:
            # Підрахунок бюджетів через ORM
            budget_plans = self.env['budget.plan'].search([
                ('cbo_id', '=', cbo.id),
                ('state', 'not in', ['draft'])
            ])
            cbo.budget_count = len(budget_plans)

    @api.depends('budget_level')
    def _compute_budget_totals(self):
        """Підрахунок загальних сум бюджетів"""
        for cbo in self:
            budget_plans = self.env['budget.plan'].search([
                ('cbo_id', '=', cbo.id),
                ('state', 'in', ['approved', 'executed'])
            ])

            cbo.total_budget_amount = sum(budget_plans.mapped('planned_amount'))
            cbo.executed_amount = sum(budget_plans.mapped('actual_amount'))

            if cbo.total_budget_amount:
                cbo.execution_rate = (cbo.executed_amount / cbo.total_budget_amount) * 100
            else:
                cbo.execution_rate = 0.0

    @api.depends('parent_id')
    def _compute_hierarchy_level(self):
        """Обчислення рівня ієрархії"""
        for cbo in self:
            level = 0
            current = cbo.parent_id
            while current:
                level += 1
                current = current.parent_id
            cbo.hierarchy_level = level

    @api.depends('name', 'parent_id', 'parent_id.full_path')
    def _compute_full_path(self):
        """Формування повного шляху"""
        for cbo in self:
            if cbo.parent_id:
                parent_path = cbo.parent_id.full_path or cbo.parent_id.name
                cbo.full_path = f"{parent_path} / {cbo.name}"
            else:
                cbo.full_path = cbo.name

    def get_tree_data(self):
        """Отримання даних для побудови дерева (для JS віджетів)"""
        self.ensure_one()

        def build_node(cbo):
            return {
                'id': cbo.id,
                'name': cbo.name,
                'code': cbo.code,
                'type': cbo.cbo_type,
                'level': cbo.budget_level,
                'icon': cbo.tree_icon,
                'color_class': cbo.tree_color_class,
                'budget_count': cbo.budget_count,
                'child_count': cbo.child_count,
                'children': [build_node(child) for child in cbo.child_ids],
                'has_children': bool(cbo.child_ids),
                'active': cbo.active,
                'responsible': cbo.responsible_user_id.name if cbo.responsible_user_id else '',
            }

        return build_node(self)

    @api.model
    def get_hierarchy_tree(self, root_id=None):
        """Отримання повного дерева ієрархії"""
        if root_id:
            root_cbos = self.browse(root_id)
        else:
            # Знаходимо корінні ЦБО (без батьків)
            root_cbos = self.search([('parent_id', '=', False)])

        return [cbo.get_tree_data() for cbo in root_cbos]

    def action_view_budgets(self):
        """Дія для перегляду бюджетів ЦБО"""
        self.ensure_one()
        return {
            'name': _('Бюджети ЦБО: %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'budget.plan',
            'view_mode': 'tree,form',
            'domain': [('cbo_id', '=', self.id)],
            'context': {
                'default_cbo_id': self.id,
                'search_default_cbo_id': self.id
            }
        }

    def action_create_budget(self):
        """Дія для створення нового бюджету"""
        self.ensure_one()
        return {
            'name': _('Новий бюджет для %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'budget.plan',
            'view_mode': 'form',
            'context': {
                'default_cbo_id': self.id,
                'default_responsible_user_id': self.responsible_user_id.id if self.responsible_user_id else False
            },
            'target': 'new'
        }

    @api.model
    def get_root_nodes(self):
        """Отримання кореневих вузлів дерева"""
        return self.search([('parent_id', '=', False), ('active', '=', True)])

    def expand_to_level(self, max_level=2):
        """Розгортання дерева до певного рівня"""

        def collect_nodes(nodes, current_level):
            result = []
            if current_level <= max_level:
                for node in nodes:
                    result.append(node)
                    if node.child_ids:
                        result.extend(collect_nodes(node.child_ids, current_level + 1))
            return result

        return collect_nodes([self], 0)

    def action_view_hierarchy(self):
        """Перегляд ієрархії ЦБО"""
        self.ensure_one()
        return {
            'name': f'Ієрархія - {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'budget.responsibility.center',
            'view_mode': 'tree,form',
            'domain': [
                '|',
                ('id', 'child_of', self.id),
                ('id', '=', self.id)
            ],
            'context': {
                'search_default_filter_active': 1,
                'tree_view_ref': 'budget.view_responsibility_center_hierarchy_tree'
            }
        }

    def action_export_tree_structure(self):
        """Експорт структури дерева"""
        self.ensure_one()

        def export_node(cbo, level=0):
            data = {
                'level': level,
                'name': cbo.name,
                'code': cbo.code,
                'type': cbo.cbo_type,
                'budget_level': cbo.budget_level,
                'responsible': cbo.responsible_user_id.name if cbo.responsible_user_id else '',
                'budget_count': cbo.budget_count,
                'total_amount': cbo.total_budget_amount,
                'execution_rate': cbo.execution_rate
            }

            result = [data]
            for child in cbo.child_ids:
                result.extend(export_node(child, level + 1))

            return result

        # Створюємо дані для експорту
        export_data = export_node(self)

        # Тут можна додати логіку для створення Excel файлу
        # або повернути дані в JSON форматі

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': _('Структуру успішно експортовано'),
                'type': 'success',
                'sticky': False,
            }
        }

    @api.model
    def create_from_template(self, template_data):
        """Створення ЦБО з шаблону"""
        created_cbos = self.env['budget.responsibility.center']

        for node_data in template_data:
            vals = {
                'name': node_data.get('name'),
                'code': node_data.get('code'),
                'cbo_type': node_data.get('cbo_type', 'department'),
                'budget_level': node_data.get('budget_level', 'operational'),
                'parent_id': node_data.get('parent_id', False),
                'responsible_user_id': node_data.get('responsible_user_id', False),
                'region': node_data.get('region', ''),
                'active': node_data.get('active', True)
            }

            cbo = self.create(vals)
            created_cbos |= cbo

        return created_cbos

    def get_statistics_dashboard(self):
        """Отримання статистики для dashboard"""
        self.ensure_one()

        # Статистика по дочірніх ЦБО
        children_stats = {}
        for child in self.child_ids:
            children_stats[child.id] = {
                'name': child.name,
                'budget_count': child.budget_count,
                'total_amount': child.total_budget_amount,
                'execution_rate': child.execution_rate
            }

        # Статистика по типах бюджетів
        budget_types_stats = self.env['budget.plan'].read_group(
            [('cbo_id', '=', self.id)],
            ['budget_type_id', 'planned_amount:sum'],
            ['budget_type_id']
        )

        return {
            'cbo_info': {
                'name': self.name,
                'code': self.code,
                'type': self.cbo_type,
                'level': self.budget_level,
                'hierarchy_level': self.hierarchy_level
            },
            'totals': {
                'budget_count': self.budget_count,
                'child_count': self.child_count,
                'total_amount': self.total_budget_amount,
                'executed_amount': self.executed_amount,
                'execution_rate': self.execution_rate
            },
            'children_stats': children_stats,
            'budget_types_stats': budget_types_stats
        }

    # МЕТОДИ ДЛЯ DASHBOARD КНОПОК
    def action_create_cbo(self):
        """Дія для створення нового ЦБО"""
        return {
            'name': _('Створити новий ЦБО'),
            'type': 'ir.actions.act_window',
            'res_model': 'budget.responsibility.center',
            'view_mode': 'form',
            'context': {
                'default_parent_id': self.id if self.id else False,
                'dashboard_mode': True
            },
            'target': 'new'
        }

    def action_view_budget_reports(self):
        """Дія для перегляду звітів по бюджетах"""
        return {
            'name': _('Звіти по бюджетах'),
            'type': 'ir.actions.act_window',
            'res_model': 'budget.plan',
            'view_mode': 'tree,form,pivot,graph',
            'domain': [('cbo_id', 'child_of', self.ids)] if self.id else [],
            'context': {
                'search_default_group_by_cbo': 1,
                'search_default_group_by_period': 1,
                'dashboard_mode': True
            }
        }

    def action_export_structure(self):
        """Дія для експорту структури"""
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Експорт структури'),
                'message': _('Функція експорту буде доступна в наступній версії'),
                'type': 'info',
                'sticky': False,
            }
        }

    @api.constrains('parent_id')
    def _check_parent_recursion(self):
        """Перевірка на рекурсивні зв'язки"""
        for cbo in self:
            if cbo.parent_id:
                current = cbo.parent_id
                visited = set()
                while current:
                    if current.id in visited:
                        raise ValidationError(
                            _('Виявлено циклічну залежність в ієрархії ЦБО. '
                              'ЦБО не може бути батьківським для самого себе.')
                        )
                    visited.add(current.id)
                    current = current.parent_id

    @api.constrains('cbo_type', 'parent_id')
    def _check_hierarchy_logic(self):
        """Перевірка логіки ієрархії типів ЦБО"""
        type_hierarchy = {
            'holding': [],
            'enterprise': ['holding'],
            'business_direction': ['holding', 'enterprise'],
            'department': ['enterprise', 'business_direction'],
            'division': ['department'],
            'office': ['department', 'division'],
            'team': ['department', 'division', 'office'],
            'project': ['department', 'division', 'office', 'team']
        }

        for cbo in self:
            if cbo.parent_id:
                allowed_parents = type_hierarchy.get(cbo.cbo_type, [])
                if allowed_parents and cbo.parent_id.cbo_type not in allowed_parents:
                    raise ValidationError(_(
                        'ЦБО типу "%s" не може мати батьківський елемент типу "%s"'
                    ) % (cbo.cbo_type, cbo.parent_id.cbo_type))

    def name_get(self):
        """Кастомне відображення назви з урахуванням ієрархії"""
        result = []
        for cbo in self:
            if cbo.code:
                name = f"[{cbo.code}] {cbo.name}"
            else:
                name = cbo.name

            # Додаємо рівень ієрархії для кращої читабельності
            if cbo.hierarchy_level > 0:
                name = "  " * cbo.hierarchy_level + name

            result.append((cbo.id, name))
        return result

    @api.model
    def _name_search(self, name, args=None, operator='ilike', limit=100, name_get_uid=None):
        """Розширений пошук по назві та коду"""
        args = args or []
        if name:
            domain = ['|', ('name', operator, name), ('code', operator, name)]
            return self._search(domain + args, limit=limit, access_rights_uid=name_get_uid)
        return super()._name_search(name, args, operator, limit, name_get_uid)

    def get_hierarchy_stats(self):
        """Статистика по ієрархії"""
        self.ensure_one()

        # Отримуємо всіх нащадків
        all_descendants = self.search([('id', 'child_of', self.id)])

        # Групуємо по типах
        type_counts = {}
        for descendant in all_descendants:
            type_counts[descendant.cbo_type] = type_counts.get(descendant.cbo_type, 0) + 1

        # Статистика бюджетів
        total_budgets = sum(all_descendants.mapped('budget_count'))
        total_amount = sum(all_descendants.mapped('total_budget_amount'))

        return {
            'total_nodes': len(all_descendants),
            'max_depth': max(all_descendants.mapped('hierarchy_level')),
            'type_distribution': type_counts,
            'total_budgets': total_budgets,
            'total_amount': total_amount,
        }

    def write(self, vals):
        """Оновлення з інвалідацією кешу для computed полів"""
        result = super().write(vals)

        # Якщо змінюється структура, оновлюємо computed поля
        if any(key in vals for key in ['parent_id', 'child_ids', 'name']):
            # Оновлюємо батьківські та дочірні записи
            all_related = self
            if 'parent_id' in vals:
                all_related |= self.mapped('parent_id')
                if vals.get('parent_id'):
                    all_related |= self.browse(vals['parent_id'])

            # Примусово перерахунок
            all_related.invalidate_recordset(['hierarchy_level', 'full_path', 'descendant_count'])

        return result