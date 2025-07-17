# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import json
import base64
from io import BytesIO


class TreeAdvancedFeatures(models.Model):
    """Розширені функції для роботи з деревом структури"""
    _inherit = 'budget.responsibility.center'

    budget_plan_id = fields.Many2one('budget.plan', 'Бюджетний план')
    # Додаткові поля для розширеної функціональності
    tree_position = fields.Integer('Позиція в дереві', default=0)
    is_expanded_by_default = fields.Boolean('Розгорнутий за замовчуванням', default=False)
    tree_icon_custom = fields.Char('Користувацька іконка', help="Emoji або CSS клас")
    tree_color = fields.Char('Колір у дереві', help="HEX код кольору")

    # Метадані дерева
    tree_metadata = fields.Text('Метадані дерева', help="JSON з додатковими даними")
    last_tree_update = fields.Datetime('Останнє оновлення дерева', default=fields.Datetime.now)

    # Статистика розширена
    total_employees = fields.Integer('Загальна кількість співробітників', compute='_compute_employee_stats')
    budget_utilization = fields.Float('Використання бюджету (%)', compute='_compute_budget_utilization')
    performance_score = fields.Float('Показник ефективності', compute='_compute_performance_score')

    @api.depends('child_ids', 'child_ids.total_employees')
    def _compute_employee_stats(self):
        """Підрахунок загальної кількості співробітників"""
        for cbo in self:
            # Базова кількість (можна додати поле employees_count)
            direct_employees = getattr(cbo, 'employees_count', 0)

            # Рекурсивний підрахунок по дочірніх ЦБО
            child_employees = sum(cbo.child_ids.mapped('total_employees'))

            cbo.total_employees = direct_employees + child_employees

    @api.depends('budget_plan_id', 'budget_plan_id')
    def _compute_budget_utilization(self):
        """Розрахунок середнього використання бюджету"""
        for cbo in self:
            active_budgets = cbo.budget_plan_id.filtered(lambda b: b.state == 'approved')
            if active_budgets:
                cbo.budget_utilization = sum(active_budgets.mapped('execution')) / len(active_budgets)
            else:
                cbo.budget_utilization = 0.0

    @api.depends('budget_utilization', 'total_employees', 'budget_count')
    def _compute_performance_score(self):
        """Розрахунок показника ефективності"""
        for cbo in self:
            # Проста формула ефективності (можна ускладнити)
            if cbo.budget_count > 0:
                efficiency = (cbo.budget_utilization / 100) * 0.7  # Вага 70%
                scale_factor = min(cbo.total_employees / 100, 1) * 0.3  # Вага 30%
                cbo.performance_score = (efficiency + scale_factor) * 100
            else:
                cbo.performance_score = 0.0

    def get_tree_json_structure(self):
        """Отримання структури дерева у JSON форматі"""

        def build_node(cbo):
            return {
                'id': cbo.id,
                'text': cbo.name,
                'code': cbo.code,
                'type': cbo.cbo_type,
                'level': cbo.budget_level,
                'icon': self._get_tree_icon(cbo),
                'color': cbo.tree_color or '#000000',
                'budget_count': cbo.budget_count,
                'child_count': cbo.child_count,
                'total_budget_amount': float(cbo.total_budget_amount or 0),
                'budget_utilization': cbo.budget_utilization,
                'performance_score': cbo.performance_score,
                'responsible_user': cbo.responsible_user_id.name if cbo.responsible_user_id else None,
                'state': {
                    'opened': cbo.is_expanded_by_default,
                    'disabled': not cbo.active,
                    'selected': False
                },
                'children': [build_node(child) for child in cbo.child_ids.sorted('sequence')]
            }

        return json.dumps([build_node(cbo) for cbo in self.filtered(lambda c: not c.parent_id)])

    def _get_tree_icon(self, cbo):
        """Отримання іконки для дерева"""
        if cbo.tree_icon_custom:
            return cbo.tree_icon_custom

        default_icons = {
            'holding': 'fa fa-university',
            'enterprise': 'fa fa-industry',
            'business_direction': 'fa fa-building',
            'department': 'fa fa-store',
            'division': 'fa fa-folder',
            'office': 'fa fa-briefcase',
            'team': 'fa fa-users',
            'project': 'fa fa-tasks'
        }
        return default_icons.get(cbo.cbo_type, 'fa fa-folder')

    def action_restructure_tree(self):
        """Wizard для реструктуризації дерева"""
        return {
            'type': 'ir.actions.act_window',
            'name': 'Реструктуризація організації',
            'res_model': 'tree.restructure.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_root_cbo_id': self.id,
                'active_model': 'budget.responsibility.center',
                'active_ids': self.ids
            }
        }

    def action_export_tree_structure(self):
        """Експорт структури дерева"""
        tree_data = self.get_tree_json_structure()

        # Створюємо Excel файл
        try:
            import xlsxwriter
            output = BytesIO()
            workbook = xlsxwriter.Workbook(output)
            worksheet = workbook.add_worksheet('Структура організації')

            # Заголовки
            headers = ['ID', 'Назва', 'Код', 'Тип', 'Рівень', 'Батьківський', 'Бюджетів', 'Співробітників']
            for col, header in enumerate(headers):
                worksheet.write(0, col, header)

            # Дані
            row = 1
            for cbo in self.search([]):
                worksheet.write(row, 0, cbo.id)
                worksheet.write(row, 1, cbo.name)
                worksheet.write(row, 2, cbo.code or '')
                worksheet.write(row, 3, cbo.cbo_type)
                worksheet.write(row, 4, cbo.budget_level)
                worksheet.write(row, 5, cbo.parent_id.name if cbo.parent_id else '')
                worksheet.write(row, 6, cbo.budget_count)
                worksheet.write(row, 7, cbo.total_employees)
                row += 1

            workbook.close()
            output.seek(0)

            # Створюємо attachment
            attachment = self.env['ir.attachment'].create({
                'name': 'Структура_організації.xlsx',
                'type': 'binary',
                'datas': base64.b64encode(output.read()),
                'res_model': self._name,
                'res_id': self.id,
                'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            })

            return {
                'type': 'ir.actions.act_url',
                'url': f'/web/content/{attachment.id}?download=true',
                'target': 'new'
            }

        except ImportError:
            # Fallback до JSON
            attachment = self.env['ir.attachment'].create({
                'name': 'tree_structure.json',
                'type': 'binary',
                'datas': base64.b64encode(tree_data.encode('utf-8')),
                'res_model': self._name,
                'res_id': self.id,
                'mimetype': 'application/json'
            })

            return {
                'type': 'ir.actions.act_url',
                'url': f'/web/content/{attachment.id}?download=true',
                'target': 'new'
            }

    def action_optimize_tree_structure(self):
        """Оптимізація структури дерева"""
        optimization_report = []

        # Пошук проблем у структурі
        problems = []

        # 1. ЦБО без батьківського (крім кореневих)
        orphaned = self.search([('parent_id', '=', False), ('cbo_type', '!=', 'holding')])
        if orphaned:
            problems.append(f"Знайдено {len(orphaned)} ЦБО без батьківського")

        # 2. Глибока вкладеність (>5 рівнів)
        deep_nested = self.search([('depth_level', '>', 5)])
        if deep_nested:
            problems.append(f"Знайдено {len(deep_nested)} ЦБО з глибокою вкладеністю")

        # 3. ЦБО без бюджетів та дочірніх (листки без функції)
        empty_leaves = self.search([
            ('child_ids', '=', False),
            ('budget_count', '=', 0),
            ('cbo_type', 'not in', ['holding'])
        ])
        if empty_leaves:
            problems.append(f"Знайдено {len(empty_leaves)} порожніх листків")

        # 4. Неоптимальний розподіл бюджетів
        unbalanced = self.search([('budget_count', '>', 20)])
        if unbalanced:
            problems.append(f"Знайдено {len(unbalanced)} ЦБО з багатьма бюджетами (>20)")

        # Рекомендації
        recommendations = []
        if orphaned:
            recommendations.append("Призначте батьківські ЦБО для відокремлених підрозділів")
        if deep_nested:
            recommendations.append("Розгляньте можливість спрощення структури")
        if empty_leaves:
            recommendations.append("Видаліть або об'єднайте порожні ЦБО")
        if unbalanced:
            recommendations.append("Розподіліть бюджети по дочірніх ЦБО")

        # Створюємо звіт
        report_content = f"""
ЗВІТ З ОПТИМІЗАЦІЇ СТРУКТУРИ ДЕРЕВА

📊 СТАТИСТИКА:
• Загалом ЦБО: {len(self.search([]))}
• Кореневих ЦБО: {len(self.search([('parent_id', '=', False)]))}
• Максимальна глибина: {max(self.search([]).mapped('depth_level') or [0])}
• Загалом бюджетів: {sum(self.search([]).mapped('budget_count'))}

⚠️ ВИЯВЛЕНІ ПРОБЛЕМИ:
{chr(10).join(f'• {problem}' for problem in problems) if problems else '• Проблем не виявлено'}

💡 РЕКОМЕНДАЦІЇ:
{chr(10).join(f'• {rec}' for rec in recommendations) if recommendations else '• Структура оптимальна'}

✅ ОПТИМІЗАЦІЯ ЗАВЕРШЕНА
        """

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Звіт з оптимізації',
                'message': report_content,
                'type': 'info',
                'sticky': True
            }
        }

    def action_bulk_update_tree_positions(self):
        """Масове оновлення позицій у дереві"""
        sequence = 10
        for cbo in self.search([('parent_id', '=', False)], order='name'):
            cbo._update_tree_positions_recursive(sequence)
            sequence += 1000

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Позиції оновлено',
                'message': 'Позиції у дереві успішно оновлено',
                'type': 'success'
            }
        }

    def _update_tree_positions_recursive(self, base_sequence):
        """Рекурсивне оновлення позицій"""
        self.sequence = base_sequence
        child_sequence = base_sequence + 10

        for child in self.child_ids.sorted('name'):
            child._update_tree_positions_recursive(child_sequence)
            child_sequence += 10

    @api.model
    def get_tree_search_suggestions(self, query):
        """Пошукові підказки для дерева"""
        if not query or len(query) < 2:
            return []

        domain = [
            '|', '|', '|',
            ('name', 'ilike', query),
            ('code', 'ilike', query),
            ('responsible_user_id.name', 'ilike', query),
            ('cbo_type', 'ilike', query)
        ]

        results = self.search(domain, limit=10)

        suggestions = []
        for result in results:
            suggestions.append({
                'id': result.id,
                'text': result.name,
                'subtitle': f"{result.code} • {result.cbo_type}",
                'icon': self._get_tree_icon(result),
                'path': result.full_path,
                'budget_count': result.budget_count
            })

        return suggestions

    def action_create_sub_cbo(self):
        """Швидке створення дочірнього ЦБО"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Новий підрозділ для {self.name}',
            'res_model': 'budget.responsibility.center',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_parent_id': self.id,
                'default_cbo_type': 'department' if self.cbo_type == 'enterprise' else 'office',
                'default_budget_level': 'operational' if self.budget_level == 'tactical' else 'functional',
                'default_company_id': self.company_ids[0].id if self.company_ids else False,
                'default_responsible_user_id': self.responsible_user_id.id
            }
        }

    def action_clone_structure(self):
        """Клонування структури ЦБО"""
        self.ensure_one()

        def clone_recursive(original, new_parent=None, suffix=" (Копія)"):
            new_cbo = original.copy({
                'name': original.name + suffix,
                'code': (original.code or '') + '_COPY',
                'parent_id': new_parent.id if new_parent else False,
                'budget_plan_ids': [(5, 0, 0)]  # Не копіюємо бюджети
            })

            # Клонуємо дочірні ЦБО
            for child in original.child_ids:
                clone_recursive(child, new_cbo, "")

            return new_cbo

        cloned = clone_recursive(self)

        return {
            'type': 'ir.actions.act_window',
            'name': 'Клонована структура',
            'res_model': 'budget.responsibility.center',
            'res_id': cloned.id,
            'view_mode': 'form',
            'target': 'current'
        }

    @api.model
    def get_tree_performance_metrics(self):
        """Метрики продуктивності дерева"""
        all_cbos = self.search([])

        metrics = {
            'total_nodes': len(all_cbos),
            'max_depth': max(all_cbos.mapped('depth_level') or [0]),
            'avg_children_per_node': sum(all_cbos.mapped('child_count')) / len(all_cbos) if all_cbos else 0,
            'nodes_with_budgets': len(all_cbos.filtered('budget_count')),
            'total_budgets': sum(all_cbos.mapped('budget_count')),
            'avg_budget_utilization': sum(all_cbos.mapped('budget_utilization')) / len(all_cbos) if all_cbos else 0,
            'performance_leaders': all_cbos.filtered(lambda c: c.performance_score > 80).mapped('name'),
            'nodes_needing_attention': all_cbos.filtered(lambda c: c.performance_score < 50).mapped('name')
        }

        return metrics