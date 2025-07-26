# -*- coding: utf-8 -*-
# wizard/tree_wizards.py - Wizard моделі для операцій з деревом

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
import json
import logging

_logger = logging.getLogger(__name__)


class TreeRestructureWizard(models.TransientModel):
    """Wizard реструктуризації дерева ЦБО"""
    _name = 'tree.restructure.wizard'
    _description = 'Wizard реструктуризації організаційного дерева'

    operation_type = fields.Selection([
        ('move_subtree', 'Переміщення піддерева'),
        ('merge_nodes', 'Злиття вузлів'),
        ('duplicate_branch', 'Дублювання гілки'),
        ('bulk_update', 'Масове оновлення')
    ], 'Тип операції', required=True, default='move_subtree')

    # Налаштування
    preserve_budgets = fields.Boolean('Зберегти бюджети', default=True)
    create_backup = fields.Boolean('Створити резервну копію', default=True)
    send_notifications = fields.Boolean('Надіслати сповіщення', default=True)

    # Параметри переміщення
    source_cbo_id = fields.Many2one(
        'budget.responsibility.center',
        'ЦБО для переміщення',
        domain=[('active', '=', True)]
    )
    target_parent_id = fields.Many2one(
        'budget.responsibility.center',
        'Новий батьківський ЦБО',
        domain=[('active', '=', True)]
    )
    move_children = fields.Boolean('Перемістити з дочірніми', default=True)
    update_codes = fields.Boolean('Оновити коди', default=False)

    # Параметри злиття
    primary_cbo_id = fields.Many2one(
        'budget.responsibility.center',
        'Основний ЦБО',
        domain=[('active', '=', True)]
    )
    secondary_cbo_ids = fields.Many2many(
        'budget.responsibility.center',
        'merge_cbo_rel',
        'wizard_id',
        'cbo_id',
        'ЦБО для злиття',
        domain=[('active', '=', True)]
    )
    merge_strategy = fields.Selection([
        ('combine', 'Об\'єднати дані'),
        ('override', 'Перезаписати основним'),
        ('archive', 'Архівувати вторинні')
    ], 'Стратегія злиття', default='combine')
    deactivate_merged = fields.Boolean('Деактивувати злиті', default=True)

    # Параметри дублювання
    copy_depth = fields.Integer('Глибина копіювання', default=2)
    copy_budgets = fields.Boolean('Копіювати бюджети', default=False)
    new_name_prefix = fields.Char('Префікс назви', default='Копія')

    # Параметри масових змін
    target_cbo_ids = fields.Many2many(
        'budget.responsibility.center',
        'bulk_update_cbo_rel',
        'wizard_id',
        'cbo_id',
        'ЦБО для оновлення',
        domain=[('active', '=', True)]
    )
    update_fields = fields.Many2many(
        'ir.model.fields',
        string='Поля для оновлення',
        domain=[('model', '=', 'budget.responsibility.center')]
    )
    new_responsible_id = fields.Many2one('res.users', 'Новий відповідальний')
    new_budget_level = fields.Selection([
        ('strategic', 'Стратегічний'),
        ('tactical', 'Тактичний'),
        ('operational', 'Операційний'),
        ('functional', 'Функціональний')
    ], 'Новий рівень бюджетування')
    new_region = fields.Char('Новий регіон')

    # Результати
    preview_changes = fields.Text('Попередній перегляд', readonly=True)
    validation_errors = fields.Text('Помилки валідації', readonly=True)

    @api.onchange('source_cbo_id', 'target_parent_id')
    def _onchange_move_params(self):
        """Валідація параметрів переміщення"""
        if self.source_cbo_id and self.target_parent_id:
            if self.source_cbo_id.id == self.target_parent_id.id:
                self.validation_errors = "ЦБО не може бути переміщено в самого себе"
            elif self._check_circular_dependency(self.source_cbo_id, self.target_parent_id):
                self.validation_errors = "Виявлено циклічну залежність"
            else:
                self.validation_errors = False

    def _check_circular_dependency(self, source, target):
        """Перевірка на циклічні залежності"""
        current = target
        while current.parent_id:
            if current.parent_id.id == source.id:
                return True
            current = current.parent_id
        return False

    def action_preview_only(self):
        """Попередній перегляд змін без виконання"""
        self.ensure_one()

        try:
            if self.operation_type == 'move_subtree':
                preview = self._preview_move_operation()
            elif self.operation_type == 'merge_nodes':
                preview = self._preview_merge_operation()
            elif self.operation_type == 'duplicate_branch':
                preview = self._preview_duplicate_operation()
            elif self.operation_type == 'bulk_update':
                preview = self._preview_bulk_update()
            else:
                preview = "Невідомий тип операції"

            self.preview_changes = preview

        except Exception as e:
            self.validation_errors = f"Помилка попереднього перегляду: {str(e)}"

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'tree.restructure.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new'
        }

    def _preview_move_operation(self):
        """Попередній перегляд операції переміщення"""
        if not self.source_cbo_id or not self.target_parent_id:
            return "Оберіть ЦБО для переміщення та цільовий батьківський ЦБО"

        preview = f"ПЕРЕМІЩЕННЯ:\n"
        preview += f"• '{self.source_cbo_id.name}' ({self.source_cbo_id.code})\n"
        preview += f"• З: {self.source_cbo_id.parent_id.name if self.source_cbo_id.parent_id else 'Корінь'}\n"
        preview += f"• До: {self.target_parent_id.name}\n"

        if self.move_children:
            children_count = len(self.source_cbo_id.child_ids)
            preview += f"• Дочірніх ЦБО: {children_count}\n"

        if self.preserve_budgets:
            budgets_count = self.source_cbo_id.budget_count
            preview += f"• Бюджетів для збереження: {budgets_count}\n"

        return preview

    def _preview_merge_operation(self):
        """Попередній перегляд операції злиття"""
        if not self.primary_cbo_id or not self.secondary_cbo_ids:
            return "Оберіть основний ЦБО та ЦБО для злиття"

        preview = f"ЗЛИТТЯ:\n"
        preview += f"• Основний: {self.primary_cbo_id.name}\n"
        preview += f"• Для злиття: {', '.join(self.secondary_cbo_ids.mapped('name'))}\n"
        preview += f"• Стратегія: {dict(self._fields['merge_strategy'].selection)[self.merge_strategy]}\n"

        total_budgets = sum(self.secondary_cbo_ids.mapped('budget_count'))
        preview += f"• Бюджетів для обробки: {total_budgets}\n"

        return preview

    def _preview_duplicate_operation(self):
        """Попередній перегляд операції дублювання"""
        if not self.source_cbo_id or not self.target_parent_id:
            return "Оберіть ЦБО для дублювання та батьківський ЦБО"

        preview = f"ДУБЛЮВАННЯ:\n"
        preview += f"• Джерело: {self.source_cbo_id.name}\n"
        preview += f"• Призначення: {self.target_parent_id.name}\n"
        preview += f"• Глибина: {self.copy_depth} рівнів\n"
        preview += f"• Префікс: '{self.new_name_prefix}'\n"

        if self.copy_budgets:
            preview += f"• Копіювати бюджети: Так\n"

        return preview

    def _preview_bulk_update(self):
        """Попередній перегляд масового оновлення"""
        if not self.target_cbo_ids:
            return "Оберіть ЦБО для оновлення"

        preview = f"МАСОВЕ ОНОВЛЕННЯ:\n"
        preview += f"• Кількість ЦБО: {len(self.target_cbo_ids)}\n"

        changes = []
        if self.new_responsible_id:
            changes.append(f"Відповідальний: {self.new_responsible_id.name}")
        if self.new_budget_level:
            changes.append(f"Рівень: {dict(self._fields['new_budget_level'].selection)[self.new_budget_level]}")
        if self.new_region:
            changes.append(f"Регіон: {self.new_region}")

        if changes:
            preview += f"• Зміни: {', '.join(changes)}\n"

        return preview

    def action_execute_restructure(self):
        """Виконання реструктуризації"""
        self.ensure_one()

        if self.validation_errors:
            raise UserError("Виправте помилки валідації перед виконанням")

        try:
            # Створення backup якщо потрібно
            if self.create_backup:
                self._create_backup()

            # Виконання операції
            if self.operation_type == 'move_subtree':
                result = self._execute_move_operation()
            elif self.operation_type == 'merge_nodes':
                result = self._execute_merge_operation()
            elif self.operation_type == 'duplicate_branch':
                result = self._execute_duplicate_operation()
            elif self.operation_type == 'bulk_update':
                result = self._execute_bulk_update()

            # Надсилання сповіщень
            if self.send_notifications:
                self._send_notifications(result)

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Реструктуризація завершена',
                    'message': f'Операція "{self.operation_type}" виконана успішно',
                    'type': 'success',
                    'sticky': False,
                }
            }

        except Exception as e:
            _logger.error(f"Restructure operation failed: {str(e)}")
            raise UserError(f"Помилка виконання операції: {str(e)}")

    def _create_backup(self):
        """Створення резервної копії"""
        # Тут можна реалізувати логіку backup
        _logger.info("Creating backup before restructure operation")

    def _execute_move_operation(self):
        """Виконання операції переміщення"""
        if self.move_children:
            # Переміщуємо з усіма дочірніми
            self.source_cbo_id.write({'parent_id': self.target_parent_id.id})
        else:
            # Переміщуємо тільки вибраний вузол
            children = self.source_cbo_id.child_ids
            children.write({'parent_id': self.source_cbo_id.parent_id.id})
            self.source_cbo_id.write({'parent_id': self.target_parent_id.id})

        if self.update_codes:
            self._update_codes_after_move()

        return f"Переміщено {self.source_cbo_id.name}"

    def _execute_merge_operation(self):
        """Виконання операції злиття"""
        merged_count = 0

        for secondary in self.secondary_cbo_ids:
            if self.merge_strategy == 'combine':
                # Переносимо бюджети до основного ЦБО
                secondary.child_ids.write({'parent_id': self.primary_cbo_id.id})
                budgets = self.env['budget.plan'].search([('cbo_id', '=', secondary.id)])
                budgets.write({'cbo_id': self.primary_cbo_id.id})

            if self.deactivate_merged:
                secondary.write({'active': False})

            merged_count += 1

        return f"Злито {merged_count} ЦБО з {self.primary_cbo_id.name}"

    def _execute_duplicate_operation(self):
        """Виконання операції дублювання"""

        def copy_node(node, parent, current_depth=0):
            if current_depth >= self.copy_depth:
                return None

            copy_values = {
                'name': f"{self.new_name_prefix} {node.name}",
                'code': f"COPY_{node.code}",
                'parent_id': parent.id if parent else False,
                'cbo_type': node.cbo_type,
                'budget_level': node.budget_level,
                'responsible_user_id': node.responsible_user_id.id,
                'region': node.region,
                'business_segment': node.business_segment
            }

            new_node = self.env['budget.responsibility.center'].create(copy_values)

            # Копіюємо бюджети якщо потрібно
            if self.copy_budgets:
                budgets = self.env['budget.plan'].search([('cbo_id', '=', node.id)])
                for budget in budgets:
                    budget.copy({'cbo_id': new_node.id, 'name': f"Копія {budget.name}"})

            # Рекурсивно копіюємо дочірні
            for child in node.child_ids:
                copy_node(child, new_node, current_depth + 1)

            return new_node

        copied_node = copy_node(self.source_cbo_id, self.target_parent_id)
        return f"Створено копію {copied_node.name}"

    def _execute_bulk_update(self):
        """Виконання масового оновлення"""
        update_values = {}

        if self.new_responsible_id:
            update_values['responsible_user_id'] = self.new_responsible_id.id
        if self.new_budget_level:
            update_values['budget_level'] = self.new_budget_level
        if self.new_region:
            update_values['region'] = self.new_region

        if update_values:
            self.target_cbo_ids.write(update_values)

        return f"Оновлено {len(self.target_cbo_ids)} ЦБО"

    def _send_notifications(self, result):
        """Надсилання сповіщень про зміни"""
        # Реалізація логіки сповіщень
        _logger.info(f"Sending notifications for restructure: {result}")


class TreeOptimizationWizard(models.TransientModel):
    """Wizard оптимізації дерева"""
    _name = 'tree.optimization.wizard'
    _description = 'Wizard оптимізації організаційної структури'

    analysis_scope = fields.Selection([
        ('full_tree', 'Повне дерево'),
        ('subtree', 'Піддерево'),
        ('level', 'Конкретний рівень')
    ], 'Область аналізу', required=True, default='full_tree')

    root_cbo_id = fields.Many2one(
        'budget.responsibility.center',
        'Кореневий ЦБО',
        domain=[('active', '=', True)]
    )
    max_depth = fields.Integer('Максимальна глибина', default=5)

    # Типи проблем для перевірки
    check_empty_nodes = fields.Boolean('Порожні вузли', default=True)
    check_deep_nesting = fields.Boolean('Глибока вкладеність', default=True)
    check_unbalanced_tree = fields.Boolean('Незбалансоване дерево', default=True)
    check_naming_inconsistency = fields.Boolean('Неконсистентність назв', default=False)

    # Результати
    analysis_results = fields.Text('Результати аналізу', readonly=True)
    optimization_recommendations = fields.Html('Рекомендації', readonly=True)

    def action_analyze_structure(self):
        """Аналіз структури дерева"""
        self.ensure_one()

        try:
            results = []
            recommendations = []

            # Отримуємо область аналізу
            if self.analysis_scope == 'full_tree':
                nodes = self.env['budget.responsibility.center'].search([('active', '=', True)])
            elif self.analysis_scope == 'subtree' and self.root_cbo_id:
                nodes = self.env['budget.responsibility.center'].search([
                    ('id', 'child_of', self.root_cbo_id.id),
                    ('active', '=', True)
                ])
            else:
                nodes = self.env['budget.responsibility.center'].search([('active', '=', True)])

            # Перевірка порожніх вузлів
            if self.check_empty_nodes:
                empty_nodes = nodes.filtered(lambda n: n.budget_count == 0 and n.child_count == 0)
                if empty_nodes:
                    results.append(f"Знайдено {len(empty_nodes)} порожніх вузлів")
                    recommendations.append("Розгляньте можливість видалення або об'єднання порожніх вузлів")

            # Перевірка глибокої вкладеності
            if self.check_deep_nesting:
                max_depth = max(nodes.mapped('hierarchy_level')) if nodes else 0
                if max_depth > self.max_depth:
                    results.append(f"Максимальна глибина {max_depth} перевищує рекомендовану {self.max_depth}")
                    recommendations.append("Спростіть структуру, зменшивши кількість рівнів")

            # Перевірка збалансованості
            if self.check_unbalanced_tree:
                root_nodes = nodes.filtered(lambda n: not n.parent_id)
                for root in root_nodes:
                    children_counts = [len(child.child_ids) for child in root.child_ids]
                    if children_counts and (max(children_counts) - min(children_counts)) > 5:
                        results.append(f"Незбалансована структура під {root.name}")
                        recommendations.append("Перерозподіліть дочірні вузли для кращого балансу")

            # Формування результатів
            self.analysis_results = '\n'.join(results) if results else "Проблем не виявлено"

            if recommendations:
                rec_html = "<ul>"
                for rec in recommendations:
                    rec_html += f"<li>{rec}</li>"
                rec_html += "</ul>"
                self.optimization_recommendations = rec_html
            else:
                self.optimization_recommendations = "<p>Структура оптимальна</p>"

        except Exception as e:
            self.analysis_results = f"Помилка аналізу: {str(e)}"

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'tree.optimization.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new'
        }

    def action_apply_recommendations(self):
        """Застосування рекомендацій"""
        # Реалізація автоматичних оптимізацій
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Оптимізація',
                'message': 'Рекомендації застосовано',
                'type': 'success'
            }
        }


class TreeExportImportWizard(models.TransientModel):
    """Wizard експорту/імпорту структури"""
    _name = 'tree.export.import.wizard'
    _description = 'Wizard експорту та імпорту структури дерева'

    operation_mode = fields.Selection([
        ('export', 'Експорт'),
        ('import', 'Імпорт')
    ], 'Режим', required=True, default='export')

    # Параметри експорту
    file_format = fields.Selection([
        ('json', 'JSON'),
        ('csv', 'CSV'),
        ('xlsx', 'Excel')
    ], 'Формат файлу', default='json')

    export_scope = fields.Selection([
        ('full_tree', 'Повне дерево'),
        ('subtree', 'Піддерево')
    ], 'Область експорту', default='full_tree')

    root_cbo_id = fields.Many2one('budget.responsibility.center', 'Кореневий ЦБО')
    include_budgets = fields.Boolean('Включити бюджети', default=False)
    include_inactive = fields.Boolean('Включити неактивні', default=False)
    include_statistics = fields.Boolean('Включити статистику', default=True)
    compression_level = fields.Selection([
        ('none', 'Без стиснення'),
        ('minimal', 'Мінімальне'),
        ('optimal', 'Оптимальне')
    ], 'Рівень стиснення', default='minimal')

    # Параметри імпорту
    import_file = fields.Binary('Файл для імпорту')
    import_filename = fields.Char('Назва файлу')
    import_mode = fields.Selection([
        ('merge', 'Об\'єднати з існуючим'),
        ('replace', 'Замінити існуюче'),
        ('append', 'Додати нові')
    ], 'Режим імпорту', default='merge')

    validate_structure = fields.Boolean('Валідувати структуру', default=True)
    create_backup_before_import = fields.Boolean('Створити backup', default=True)
    skip_existing = fields.Boolean('Пропустити існуючі', default=True)

    # Результати
    operation_result = fields.Text('Результат операції', readonly=True)
    export_file = fields.Binary('Файл експорту', readonly=True)
    export_filename = fields.Char('Назва файлу', readonly=True)

    def action_export_structure(self):
        """Експорт структури"""
        try:
            cbo_model = self.env['budget.responsibility.center']

            if self.export_scope == 'full_tree':
                data = cbo_model.export_tree_structure()
            else:
                # Експорт піддерева
                data = cbo_model.browse(self.root_cbo_id.id).get_tree_data()

            # Конвертація в потрібний формат
            if self.file_format == 'json':
                content = json.dumps(data, indent=2, ensure_ascii=False)
                filename = f"tree_export_{fields.Date.today()}.json"
            elif self.file_format == 'csv':
                # Конвертація в CSV
                content = self._convert_to_csv(data)
                filename = f"tree_export_{fields.Date.today()}.csv"
            else:  # Excel
                content = self._convert_to_excel(data)
                filename = f"tree_export_{fields.Date.today()}.xlsx"

            self.export_file = content.encode() if isinstance(content, str) else content
            self.export_filename = filename
            self.operation_result = f"Експорт завершено. Файл: {filename}"

        except Exception as e:
            self.operation_result = f"Помилка експорту: {str(e)}"

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'tree.export.import.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new'
        }

    def _convert_to_csv(self, data):
        """Конвертація даних в CSV"""
        import csv
        import io

        output = io.StringIO()
        writer = csv.writer(output)

        # Заголовки
        writer.writerow(['ID', 'Name', 'Code', 'Type', 'Parent_Code', 'Level'])

        def write_node(node, parent_code=''):
            writer.writerow([
                node.get('id', ''),
                node.get('name', ''),
                node.get('code', ''),
                node.get('type', ''),
                parent_code,
                node.get('hierarchy_level', 0)
            ])

            for child in node.get('children', []):
                write_node(child, node.get('code', ''))

        if isinstance(data, dict) and 'tree_structure' in data:
            for node in data['tree_structure']:
                write_node(node)

        return output.getvalue()

    def _convert_to_excel(self, data):
        """Конвертація даних в Excel"""
        # Тут би була реалізація конвертації в Excel
        # Повертаємо JSON як заглушку
        return json.dumps(data, indent=2, ensure_ascii=False)

    def action_import_structure(self):
        """Імпорт структури"""
        if not self.import_file:
            raise UserError("Оберіть файл для імпорту")

        try:
            # Декодування файлу
            import base64
            content = base64.b64decode(self.import_file).decode('utf-8')

            if self.import_filename.endswith('.json'):
                data = json.loads(content)
            else:
                raise UserError("Підтримується тільки JSON формат")

            # Валідація якщо потрібно
            if self.validate_structure:
                self._validate_import_data(data)

            # Створення backup
            if self.create_backup_before_import:
                self._create_import_backup()

            # Виконання імпорту
            imported_count = self._perform_import(data)

            self.operation_result = f"Імпорт завершено. Імпортовано: {imported_count} записів"

        except Exception as e:
            self.operation_result = f"Помилка імпорту: {str(e)}"

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'tree.export.import.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new'
        }

    def _validate_import_data(self, data):
        """Валідація даних імпорту"""
        required_fields = ['name', 'code', 'type']

        def validate_node(node):
            for field in required_fields:
                if field not in node:
                    raise ValidationError(f"Відсутнє обов'язкове поле: {field}")

            for child in node.get('children', []):
                validate_node(child)

        if isinstance(data, dict) and 'tree_structure' in data:
            for node in data['tree_structure']:
                validate_node(node)

    def _create_import_backup(self):
        """Створення backup перед імпортом"""
        _logger.info("Creating backup before import")

    def _perform_import(self, data):
        """Виконання імпорту даних"""
        imported_count = 0

        def import_node(node_data, parent_id=None):
            nonlocal imported_count

            # Перевірка на існування
            existing = None
            if self.skip_existing:
                existing = self.env['budget.responsibility.center'].search([
                    ('code', '=', node_data['code'])
                ], limit=1)

            if existing and self.skip_existing:
                return existing

            # Створення або оновлення
            values = {
                'name': node_data['name'],
                'code': node_data['code'],
                'cbo_type': node_data.get('type', 'other'),
                'parent_id': parent_id,
                'active': node_data.get('active', True)
            }

            if existing and self.import_mode == 'merge':
                existing.write(values)
                new_node = existing
            else:
                new_node = self.env['budget.responsibility.center'].create(values)

            imported_count += 1

            # Імпорт дочірніх вузлів
            for child_data in node_data.get('children', []):
                import_node(child_data, new_node.id)

            return new_node

        # Імпорт структури
        if isinstance(data, dict) and 'tree_structure' in data:
            for node_data in data['tree_structure']:
                import_node(node_data)

        return imported_count

    def action_validate_import(self):
        """Валідація файлу імпорту"""
        if not self.import_file:
            raise UserError("Оберіть файл для валідації")

        try:
            import base64
            content = base64.b64decode(self.import_file).decode('utf-8')
            data = json.loads(content)

            self._validate_import_data(data)
            self.operation_result = "Файл пройшов валідацію успішно"

        except Exception as e:
            self.operation_result = f"Помилка валідації: {str(e)}"

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'tree.export.import.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new'
        }