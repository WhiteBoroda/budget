# -*- coding: utf-8 -*-
# Додаткові методи для моделі budget.responsibility.center - TREE FUNCTIONALITY

from odoo import models, api, fields, _
from odoo.exceptions import ValidationError, UserError
import json
import logging

_logger = logging.getLogger(__name__)


class ResponsibilityCenterTreeMethods(models.Model):
    """Методи для роботи з деревом ЦБО"""
    _inherit = 'budget.responsibility.center'

    @api.model
    def get_hierarchy_tree(self, include_inactive=False, max_depth=10):
        """Отримання даних ієрархічного дерева для JavaScript віджетів"""
        try:
            domain = [('parent_id', '=', False)]
            if not include_inactive:
                domain.append(('active', '=', True))

            root_nodes = self.search(domain, order='sequence, name')

            def build_tree_data(nodes, current_depth=0):
                if current_depth >= max_depth:
                    return []

                tree_data = []
                for node in nodes:
                    # Базова інформація про вузол
                    node_data = {
                        'id': node.id,
                        'name': node.name,
                        'code': node.code,
                        'type': node.cbo_type,
                        'level': node.budget_level,
                        'active': node.active,
                        'budget_count': node.budget_count,
                        'child_count': node.child_count,
                        'responsible': node.responsible_user_id.name if node.responsible_user_id else '',
                        'region': node.region or '',
                        'sequence': node.sequence,
                        'has_children': bool(node.child_ids),
                        'hierarchy_level': current_depth
                    }

                    # Дочірні вузли
                    if node.child_ids and current_depth < max_depth - 1:
                        child_domain = [('parent_id', '=', node.id)]
                        if not include_inactive:
                            child_domain.append(('active', '=', True))

                        children = self.search(child_domain, order='sequence, name')
                        node_data['children'] = build_tree_data(children, current_depth + 1)
                    else:
                        node_data['children'] = []

                    tree_data.append(node_data)

                return tree_data

            return build_tree_data(root_nodes)

        except Exception as e:
            _logger.error(f"Error building hierarchy tree: {str(e)}")
            return []

    @api.model
    def get_advanced_tree_data(self, include_analytics=False, include_inactive=False, max_depth=10):
        """Розширені дані дерева з аналітикою"""
        try:
            tree_data = self.get_hierarchy_tree(include_inactive, max_depth)

            result = {
                'tree': tree_data,
                'total_nodes': len(self.search([])),
                'active_nodes': len(self.search([('active', '=', True)])),
                'max_depth': self._get_max_hierarchy_depth(),
                'last_updated': fields.Datetime.now().isoformat()
            }

            if include_analytics:
                result['analytics'] = self.get_tree_analytics()

            return result

        except Exception as e:
            _logger.error(f"Error building advanced tree data: {str(e)}")
            return {'tree': [], 'error': str(e)}

    @api.model
    def get_tree_analytics(self):
        """Аналітика по дереву ЦБО"""
        try:
            all_cbos = self.search([])
            active_cbos = all_cbos.filtered('active')

            # Статистика по типах
            type_stats = {}
            for cbo in active_cbos:
                cbo_type = cbo.cbo_type
                if cbo_type not in type_stats:
                    type_stats[cbo_type] = {
                        'count': 0,
                        'with_budgets': 0,
                        'total_budgets': 0
                    }

                type_stats[cbo_type]['count'] += 1
                if cbo.budget_count > 0:
                    type_stats[cbo_type]['with_budgets'] += 1
                    type_stats[cbo_type]['total_budgets'] += cbo.budget_count

            # Статистика по рівнях ієрархії
            level_stats = {}
            for cbo in active_cbos:
                level = cbo.hierarchy_level
                if level not in level_stats:
                    level_stats[level] = 0
                level_stats[level] += 1

            # Топ ЦБО по бюджетах
            top_cbos = active_cbos.sorted('budget_count', reverse=True)[:10]
            top_cbos_data = [{
                'id': cbo.id,
                'name': cbo.name,
                'budget_count': cbo.budget_count,
                'total_amount': cbo.total_budget_amount
            } for cbo in top_cbos]

            return {
                'total_nodes': len(all_cbos),
                'active_nodes': len(active_cbos),
                'inactive_nodes': len(all_cbos) - len(active_cbos),
                'max_depth': self._get_max_hierarchy_depth(),
                'type_distribution': type_stats,
                'level_distribution': level_stats,
                'top_cbos_by_budgets': top_cbos_data,
                'nodes_with_budgets': len(active_cbos.filtered(lambda c: c.budget_count > 0)),
                'nodes_without_budgets': len(active_cbos.filtered(lambda c: c.budget_count == 0)),
                'total_budgets': sum(active_cbos.mapped('budget_count')),
                'avg_budgets_per_cbo': sum(active_cbos.mapped('budget_count')) / len(active_cbos) if active_cbos else 0
            }

        except Exception as e:
            _logger.error(f"Error getting tree analytics: {str(e)}")
            return {}

    def _get_max_hierarchy_depth(self):
        """Отримання максимальної глибини ієрархії"""
        max_depth = 0
        for cbo in self.search([]):
            depth = cbo.hierarchy_level
            if depth > max_depth:
                max_depth = depth
        return max_depth

    @api.model
    def get_stats_summary(self):
        """Зведена статистика для простих віджетів"""
        try:
            active_cbos = self.search([('active', '=', True)])

            # Підрахунок активних бюджетів
            total_budgets = self.env['budget.plan'].search_count([
                ('cbo_id', 'in', active_cbos.ids),
                ('state', 'in', ['approved', 'executed'])
            ])

            return {
                'total_cbos': len(active_cbos),
                'active_budgets': total_budgets,
                'cbos_with_budgets': len(active_cbos.filtered(lambda c: c.budget_count > 0)),
                'last_updated': fields.Datetime.now().isoformat()
            }

        except Exception as e:
            _logger.error(f"Error getting stats summary: {str(e)}")
            return {
                'total_cbos': 0,
                'active_budgets': 0,
                'cbos_with_budgets': 0,
                'error': True
            }

    @api.model
    def bulk_operation(self, cbo_ids, operation):
        """Масові операції з ЦБО"""
        cbos = self.browse(cbo_ids)

        if operation == 'activate':
            cbos.write({'active': True})
        elif operation == 'deactivate':
            cbos.write({'active': False})
        elif operation == 'update_responsible':
            # Відкриваємо wizard для масового призначення відповідального
            return {
                'name': 'Масове призначення відповідального',
                'type': 'ir.actions.act_window',
                'res_model': 'bulk.responsible.wizard',
                'view_mode': 'form',
                'target': 'new',
                'context': {'default_cbo_ids': cbo_ids}
            }
        elif operation == 'export':
            return self.export_nodes(cbo_ids)
        else:
            raise UserError(f"Невідома операція: {operation}")

        return True

    @api.model
    def export_nodes(self, cbo_ids):
        """Експорт вузлів дерева"""
        cbos = self.browse(cbo_ids)

        export_data = []
        for cbo in cbos:
            cbo_data = {
                'name': cbo.name,
                'code': cbo.code,
                'cbo_type': cbo.cbo_type,
                'budget_level': cbo.budget_level,
                'parent_code': cbo.parent_id.code if cbo.parent_id else None,
                'responsible_email': cbo.responsible_user_id.email if cbo.responsible_user_id else None,
                'region': cbo.region,
                'business_segment': cbo.business_segment,
                'active': cbo.active,
                'sequence': cbo.sequence,
                'budget_count': cbo.budget_count,
                'child_count': cbo.child_count
            }
            export_data.append(cbo_data)

        return export_data

    @api.model
    def export_tree_structure(self):
        """Експорт повної структури дерева"""
        try:
            tree_data = self.get_hierarchy_tree(include_inactive=True)

            export_structure = {
                'export_date': fields.Datetime.now().isoformat(),
                'company': self.env.company.name,
                'total_nodes': len(self.search([])),
                'tree_structure': tree_data,
                'metadata': {
                    'odoo_version': '17.0',
                    'module': 'budget',
                    'export_format': 'json'
                }
            }

            return export_structure

        except Exception as e:
            _logger.error(f"Error exporting tree structure: {str(e)}")
            raise UserError(f"Помилка експорту: {str(e)}")

    def action_view_tree_structure(self):
        """Відкриття дерева структури для поточного ЦБО"""
        self.ensure_one()

        return {
            'name': f'Структура - {self.name}',
            'type': 'ir.actions.client',
            'tag': 'budget_hierarchy_tree_widget',
            'context': {
                'default_cbo_id': self.id,
                'show_children': True
            }
        }

    def get_breadcrumb_path(self):
        """Отримання хлібних крихт для навігації"""
        self.ensure_one()

        path = []
        current = self
        while current:
            path.insert(0, {
                'id': current.id,
                'name': current.name,
                'code': current.code
            })
            current = current.parent_id

        return path

    def get_siblings(self):
        """Отримання сусідніх ЦБО на тому ж рівні"""
        self.ensure_one()

        domain = [('parent_id', '=', self.parent_id.id if self.parent_id else False)]
        if self.id:
            domain.append(('id', '!=', self.id))

        return self.search(domain, order='sequence, name')

    @api.model
    def search_tree_nodes(self, query, filters=None):
        """Пошук вузлів в дереві з фільтрами"""
        domain = []

        # Текстовий пошук
        if query:
            domain.extend([
                '|', '|',
                ('name', 'ilike', query),
                ('code', 'ilike', query),
                ('region', 'ilike', query)
            ])

        # Фільтри
        if filters:
            if 'type' in filters:
                domain.append(('cbo_type', '=', filters['type']))
            if 'level' in filters:
                domain.append(('budget_level', '=', filters['level']))
            if 'has_budgets' in filters:
                if filters['has_budgets']:
                    domain.append(('budget_count', '>', 0))
                else:
                    domain.append(('budget_count', '=', 0))
            if 'active' in filters:
                domain.append(('active', '=', filters['active']))

        return self.search(domain, order='hierarchy_level, sequence, name')

    def action_optimize_structure(self):
        """Оптимізація структури дерева"""
        self.ensure_one()

        return {
            'name': 'Оптимізація структури',
            'type': 'ir.actions.act_window',
            'res_model': 'tree.optimization.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_root_cbo_id': self.id,
                'default_analysis_scope': 'subtree'
            }
        }

    def _compute_performance_metrics(self):
        """Обчислення метрик продуктивності ЦБО"""
        for cbo in self:
            budgets = self.env['budget.plan'].search([
                ('cbo_id', '=', cbo.id),
                ('state', 'in', ['approved', 'executed'])
            ])

            if budgets:
                total_planned = sum(budgets.mapped('planned_amount'))
                total_actual = sum(budgets.mapped('actual_amount'))

                cbo.avg_execution_rate = (total_actual / total_planned * 100) if total_planned > 0 else 0
                cbo.performance_score = min(100, cbo.avg_execution_rate)
            else:
                cbo.avg_execution_rate = 0.0
                cbo.performance_score = 0.0

    # Computed поля для метрик продуктивності
    avg_execution_rate = fields.Float(
        'Середній рівень виконання, %',
        compute='_compute_performance_metrics',
        store=False,
        help="Середній відсоток виконання бюджетів"
    )

    performance_score = fields.Float(
        'Оцінка продуктивності',
        compute='_compute_performance_metrics',
        store=False,
        help="Загальна оцінка продуктивності ЦБО"
    )