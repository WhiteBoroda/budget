# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class TreeRestructureWizard(models.TransientModel):
    """Wizard для реструктуризації дерева організації"""
    _name = 'tree.restructure.wizard'
    _description = 'Майстер реструктуризації дерева'

    operation_type = fields.Selection([
        ('move_subtree', 'Перемістити піддерево'),
        ('merge_nodes', 'Об\'єднати вузли'),
        ('split_node', 'Розділити вузол'),
        ('optimize_structure', 'Оптимізувати структуру'),
        ('bulk_update', 'Масове оновлення')
    ], 'Тип операції', required=True, default='move_subtree')

    # Параметри для переміщення
    source_cbo_id = fields.Many2one('budget.responsibility.center', 'Джерело (що переміщуємо)')
    target_parent_id = fields.Many2one('budget.responsibility.center', 'Новий батьківський ЦБО')

    # Параметри для об'єднання
    primary_cbo_id = fields.Many2one('budget.responsibility.center', 'Основний ЦБО (залишиться)')
    secondary_cbo_ids = fields.Many2many('budget.responsibility.center',
                                         'wizard_secondary_cbo_rel',
                                         string='ЦБО для об\'єднання (будуть видалені)')

    # Параметри для розділення
    split_cbo_id = fields.Many2one('budget.responsibility.center', 'ЦБО для розділення')
    new_cbo_names = fields.Text('Назви нових ЦБО (по одній в рядку)')
    split_criteria = fields.Selection([
        ('by_budget_type', 'По типах бюджетів'),
        ('by_department', 'По підрозділах'),
        ('by_geography', 'По географії'),
        ('manual', 'Ручний розподіл')
    ], 'Критерій розділення', default='manual')

    # Масове оновлення
    update_fields = fields.Selection([
        ('responsible_users', 'Відповідальні користувачі'),
        ('cbo_types', 'Типи ЦБО'),
        ('budget_levels', 'Рівні бюджетування'),
        ('sequences', 'Послідовності'),
        ('all', 'Всі поля')
    ], 'Поля для оновлення')

    # Налаштування операції
    preserve_budgets = fields.Boolean('Зберегти бюджети', default=True)
    create_backup = fields.Boolean('Створити резервну копію', default=True)
    send_notifications = fields.Boolean('Відправити сповіщення', default=True)

    # Попередній перегляд
    preview_changes = fields.Text('Попередній перегляд змін', readonly=True)
    validation_errors = fields.Text('Помилки валідації', readonly=True)

    @api.onchange('operation_type', 'source_cbo_id', 'target_parent_id')
    def _onchange_operation_params(self):
        """Валідація та попередній перегляд змін"""
        self._validate_operation()
        self._generate_preview()

    def _validate_operation(self):
        """Валідація параметрів операції"""
        errors = []

        if self.operation_type == 'move_subtree':
            if not self.source_cbo_id:
                errors.append("Оберіть ЦБО для переміщення")
            elif not self.target_parent_id:
                errors.append("Оберіть новий батьківський ЦБО")
            elif self.source_cbo_id == self.target_parent_id:
                errors.append("ЦБО не може бути батьком самого себе")
            elif self._would_create_cycle():
                errors.append("Операція створить циклічну залежність")

        elif self.operation_type == 'merge_nodes':
            if not self.primary_cbo_id:
                errors.append("Оберіть основний ЦБО")
            elif not self.secondary_cbo_ids:
                errors.append("Оберіть ЦБО для об'єднання")
            elif self.primary_cbo_id in self.secondary_cbo_ids:
                errors.append("Основний ЦБО не може бути в списку для об'єднання")

        elif self.operation_type == 'split_node':
            if not self.split_cbo_id:
                errors.append("Оберіть ЦБО для розділення")
            elif not self.new_cbo_names:
                errors.append("Вкажіть назви нових ЦБО")

        self.validation_errors = '\n'.join(errors) if errors else False

    def _would_create_cycle(self):
        """Перевірка на циклічну залежність"""
        if not self.source_cbo_id or not self.target_parent_id:
            return False

        # Перевіряємо, чи target_parent не є нащадком source
        current = self.target_parent_id
        while current:
            if current == self.source_cbo_id:
                return True
            current = current.parent_id
        return False

    def _generate_preview(self):
        """Генерація попереднього перегляду змін"""
        if self.validation_errors:
            self.preview_changes = "❌ Спочатку виправте помилки валідації"
            return

        preview_lines = []

        if self.operation_type == 'move_subtree' and self.source_cbo_id and self.target_parent_id:
            affected_count = 1 + len(self.source_cbo_id.get_descendants())
            budget_count = sum((self.source_cbo_id | self.source_cbo_id.get_descendants()).mapped('budget_count'))

            preview_lines.extend([
                f"🔄 ПЕРЕМІЩЕННЯ ПІДДЕРЕВА:",
                f"• Джерело: {self.source_cbo_id.name}",
                f"• Новий батько: {self.target_parent_id.name}",
                f"• Буде переміщено: {affected_count} ЦБО",
                f"• Буде переміщено: {budget_count} бюджетів",
                "",
                f"📊 НОВА СТРУКТУРА:",
                f"{self.target_parent_id.name}",
                f"  └── {self.source_cbo_id.name} (переміщено)"
            ])

        elif self.operation_type == 'merge_nodes' and self.primary_cbo_id and self.secondary_cbo_ids:
            total_budgets = sum(self.secondary_cbo_ids.mapped('budget_count'))
            total_children = sum(self.secondary_cbo_ids.mapped('child_count'))

            preview_lines.extend([
                f"🔀 ОБ'ЄДНАННЯ ВУЗЛІВ:",
                f"• Основний ЦБО: {self.primary_cbo_id.name} (залишиться)",
                f"• Для об'єднання: {', '.join(self.secondary_cbo_ids.mapped('name'))}",
                f"• Буде перенесено: {total_budgets} бюджетів",
                f"• Буде перенесено: {total_children} дочірніх ЦБО",
                "",
                f"⚠️ ЦБО для об'єднання будуть ВИДАЛЕНІ!"
            ])

        elif self.operation_type == 'split_node' and self.split_cbo_id and self.new_cbo_names:
            new_names = [name.strip() for name in self.new_cbo_names.split('\n') if name.strip()]

            preview_lines.extend([
                f"✂️ РОЗДІЛЕННЯ ВУЗЛА:",
                f"• Джерело: {self.split_cbo_id.name}",
                f"• Нові ЦБО: {', '.join(new_names)}",
                f"• Критерій: {dict(self._fields['split_criteria'].selection)[self.split_criteria]}",
                f"• Бюджетів для розподілу: {self.split_cbo_id.budget_count}",
                "",
                f"📋 РЕЗУЛЬТАТ:",
                *[f"  • {name}" for name in new_names]
            ])

        self.preview_changes = '\n'.join(preview_lines) if preview_lines else "Оберіть параметри для перегляду"

    def action_execute_restructure(self):
        """Виконання реструктуризації"""
        if self.validation_errors:
            raise UserError("Виправте помилки валідації перед виконанням")

        # Створення резервної копії
        if self.create_backup:
            self._create_backup()

        try:
            if self.operation_type == 'move_subtree':
                self._execute_move_subtree()
            elif self.operation_type == 'merge_nodes':
                self._execute_merge_nodes()
            elif self.operation_type == 'split_node':
                self._execute_split_node()
            elif self.operation_type == 'optimize_structure':
                self._execute_optimize_structure()
            elif self.operation_type == 'bulk_update':
                self._execute_bulk_update()

            # Відправка сповіщень
            if self.send_notifications:
                self._send_notifications()

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Реструктуризація завершена!',
                    'message': 'Операція успішно виконана. Структура дерева оновлена.',
                    'type': 'success',
                    'sticky': True
                }
            }

        except Exception as e:
            raise UserError(f"Помилка під час реструктуризації: {str(e)}")

    def _execute_move_subtree(self):
        """Виконання переміщення піддерева"""
        self.source_cbo_id.write({
            'parent_id': self.target_parent_id.id,
            'last_tree_update': fields.Datetime.now()
        })

        # Оновлюємо послідовності
        self._update_sequences_after_move()

    def _execute_merge_nodes(self):
        """Виконання об'єднання вузлів"""
        primary = self.primary_cbo_id

        for secondary in self.secondary_cbo_ids:
            # Переносимо бюджети
            if self.preserve_budgets:
                secondary.budget_plan_ids.write({'cbo_id': primary.id})

            # Переносимо дочірні ЦБО
            secondary.child_ids.write({'parent_id': primary.id})

            # Об'єднуємо додаткові дані
            if secondary.responsible_user_id and not primary.responsible_user_id:
                primary.responsible_user_id = secondary.responsible_user_id

            # Видаляємо вторинний ЦБО
            secondary.unlink()

    def _execute_split_node(self):
        """Виконання розділення вузла"""
        source = self.split_cbo_id
        new_names = [name.strip() for name in self.new_cbo_names.split('\n') if name.strip()]

        created_cbos = []

        for name in new_names:
            new_cbo = source.copy({
                'name': name,
                'code': f"{source.code}_{len(created_cbos) + 1}" if source.code else f"SPLIT_{len(created_cbos) + 1}",
                'parent_id': source.parent_id.id,
                'budget_plan_ids': [(5, 0, 0)],  # Очищуємо бюджети
                'child_ids': [(5, 0, 0)]  # Очищуємо дочірні
            })
            created_cbos.append(new_cbo)

        # Розподіляємо бюджети
        if self.preserve_budgets:
            self._distribute_budgets(source, created_cbos)

        # Розподіляємо дочірні ЦБО
        self._distribute_children(source, created_cbos)

        # Видаляємо оригінальний ЦБО
        source.unlink()

    def _distribute_budgets(self, source_cbo, target_cbos):
        """Розподіл бюджетів між новими ЦБО"""
        budgets = source_cbo.budget_plan_ids

        if self.split_criteria == 'by_budget_type':
            # Групуємо по типах бюджетів
            budget_types = budgets.mapped('budget_type_id')
            for i, budget_type in enumerate(budget_types):
                target_cbo = target_cbos[i % len(target_cbos)]
                budgets.filtered(lambda b: b.budget_type_id == budget_type).write({
                    'cbo_id': target_cbo.id
                })
        else:
            # Рівномірний розподіл
            for i, budget in enumerate(budgets):
                target_cbo = target_cbos[i % len(target_cbos)]
                budget.cbo_id = target_cbo.id

    def _distribute_children(self, source_cbo, target_cbos):
        """Розподіл дочірніх ЦБО"""
        children = source_cbo.child_ids

        for i, child in enumerate(children):
            target_cbo = target_cbos[i % len(target_cbos)]
            child.parent_id = target_cbo.id

    def _execute_optimize_structure(self):
        """Оптимізація структури"""
        # Автоматичне виправлення типових проблем

        # 1. Виправлення глибокої вкладеності
        deep_nested = self.env['budget.responsibility.center'].search([('depth_level', '>', 5)])
        for cbo in deep_nested:
            # Піднімаємо на 2 рівні вгору
            if cbo.parent_id and cbo.parent_id.parent_id:
                cbo.parent_id = cbo.parent_id.parent_id

        # 2. Об'єднання порожніх листків з батьківськими
        empty_leaves = self.env['budget.responsibility.center'].search([
            ('child_ids', '=', False),
            ('budget_count', '=', 0),
            ('cbo_type', 'not in', ['holding'])
        ])

        for leaf in empty_leaves:
            if leaf.parent_id and leaf.parent_id.child_count == 1:
                # Єдина дитина без функції - видаляємо
                leaf.unlink()

    def _execute_bulk_update(self):
        """Масове оновлення полів"""
        cbos = self.env.context.get('active_ids', [])
        if not cbos:
            return

        cbo_records = self.env['budget.responsibility.center'].browse(cbos)

        if self.update_fields == 'sequences':
            cbo_records.action_bulk_update_tree_positions()
        elif self.update_fields == 'all':
            # Масове оновлення всіх полів
            cbo_records._compute_budget_stats()
            cbo_records._compute_child_count()
            cbo_records._compute_depth_level()

    def _create_backup(self):
        """Створення резервної копії структури"""
        backup_data = []
        all_cbos = self.env['budget.responsibility.center'].search([])

        for cbo in all_cbos:
            backup_data.append({
                'id': cbo.id,
                'name': cbo.name,
                'code': cbo.code,
                'parent_id': cbo.parent_id.id if cbo.parent_id else None,
                'cbo_type': cbo.cbo_type,
                'sequence': cbo.sequence
            })

        # Зберігаємо як attachment
        import json
        backup_json = json.dumps(backup_data, indent=2)

        self.env['ir.attachment'].create({
            'name': f'tree_backup_{fields.Datetime.now().strftime("%Y%m%d_%H%M%S")}.json',
            'type': 'binary',
            'datas': base64.b64encode(backup_json.encode('utf-8')),
            'res_model': 'tree.restructure.wizard',
            'res_id': self.id
        })

    def _update_sequences_after_move(self):
        """Оновлення послідовностей після переміщення"""
        if self.target_parent_id:
            children = self.target_parent_id.child_ids.sorted('name')
            for i, child in enumerate(children):
                child.sequence = (i + 1) * 10

    def _send_notifications(self):
        """Відправка сповіщень про зміни"""
        affected_users = set()

        # Збираємо користувачів, яких потрібно сповістити
        if hasattr(self, 'source_cbo_id') and self.source_cbo_id:
            if self.source_cbo_id.responsible_user_id:
                affected_users.add(self.source_cbo_id.responsible_user_id)

        if hasattr(self, 'target_parent_id') and self.target_parent_id:
            if self.target_parent_id.responsible_user_id:
                affected_users.add(self.target_parent_id.responsible_user_id)

        # Відправляємо сповіщення
        for user in affected_users:
            self.env['mail.activity'].create({
                'activity_type_id': self.env.ref('mail.mail_activity_data_todo').id,
                'user_id': user.id,
                'res_model': 'budget.responsibility.center',
                'res_id': getattr(self, 'source_cbo_id', self.env['budget.responsibility.center']).id,
                'summary': 'Зміна в структурі організації',
                'note': f'Проведено реструктуризацію дерева організації. Перевірте актуальність ваших бюджетів та відповідальності.'
            })

    def action_preview_only(self):
        """Тільки попередній перегляд без виконання"""
        self._validate_operation()
        self._generate_preview()

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'tree.restructure.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'context': {'preview_mode': True}
        }