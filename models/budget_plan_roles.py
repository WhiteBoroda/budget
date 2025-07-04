from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from datetime import date, timedelta


class BudgetPlan(models.Model):
    """Розширення моделі budget.plan для інтеграції з бізнес-ролями"""
    _inherit = 'budget.plan'

    # ==================================================
    # НОВІ ПОЛЯ ДЛЯ БІЗНЕС-РОЛЕЙ
    # ==================================================

    # Прив'язка до бізнес-ролей
    budget_creator_role_id = fields.Many2one(
        'business.role.catalog',
        string='Роль "Складач бюджету"',
        domain=[('role', 'ilike', 'Складач')],
        help='Бізнес-роль для складання бюджету'
    )

    budget_reviewer_role_id = fields.Many2one(
        'business.role.catalog',
        string='Роль "Перевіряючий бюджету"',
        domain=[('role', 'ilike', 'Перевір')],
        help='Бізнес-роль для перевірки бюджету'
    )

    budget_approver_role_id = fields.Many2one(
        'business.role.catalog',
        string='Роль "Затверджуючий бюджету"',
        domain=[('role', 'ilike', 'Затвердж')],
        help='Бізнес-роль для затвердження бюджету'
    )

    # Обчислювальні поля для визначення виконавців ролей
    current_creator_ids = fields.Many2many(
        'res.users',
        compute='_compute_current_executors',
        string='Поточні складачі бюджету'
    )

    current_reviewer_ids = fields.Many2many(
        'res.users',
        compute='_compute_current_executors',
        string='Поточні перевіряючі бюджету'
    )

    current_approver_ids = fields.Many2many(
        'res.users',
        compute='_compute_current_executors',
        string='Поточні затверджуючі бюджету'
    )

    # Використання системи ролей для затвердження
    use_role_based_approval = fields.Boolean(
        'Використовувати систему ролей',
        default=True,
        help='Якщо відмічено, використовуватиметься система бізнес-ролей для визначення відповідальних'
    )

    # Адресація для ролей (зв'язок з ЦБО)
    role_addressing_model_1 = fields.Char(
        string='Модель адресації 1',
        default='budget.responsibility.center',
        help='Модель для першого рівня адресації ролей'
    )

    role_addressing_id_1 = fields.Many2oneReference(
        model_field='role_addressing_model_1',
        string='Адресація ролей (ЦБО)',
        help='ЦБО для якого призначаються ролі'
    )

    # ==================================================
    # ОБЧИСЛЕННЯ ВИКОНАВЦІВ РОЛЕЙ
    # ==================================================

    @api.depends('budget_creator_role_id', 'budget_reviewer_role_id',
                 'budget_approver_role_id', 'cbo_id', 'use_role_based_approval')
    def _compute_current_executors(self):
        """Обчислення поточних виконавців бізнес-ролей"""
        for record in self:
            if not record.use_role_based_approval:
                record.current_creator_ids = False
                record.current_reviewer_ids = False
                record.current_approver_ids = False
                continue

            today = fields.Date.today()

            # Складачі бюджету
            record.current_creator_ids = record._get_role_executors(
                record.budget_creator_role_id, today
            )

            # Перевіряючі бюджету
            record.current_reviewer_ids = record._get_role_executors(
                record.budget_reviewer_role_id, today
            )

            # Затверджуючі бюджету
            record.current_approver_ids = record._get_role_executors(
                record.budget_approver_role_id, today
            )

    def _get_role_executors(self, role_catalog, target_date):
        """Пошук виконавців конкретної ролі на певну дату"""
        if not role_catalog:
            return self.env['res.users']

        # Шукаємо активних виконавців ролі
        domain = [
            ('role_id', '=', role_catalog.id),
            ('date', '<=', target_date),
            ('status_role', '=', True)
        ]

        # Додаємо адресацію якщо налаштована
        if self.cbo_id and role_catalog.addressed:
            if role_catalog.first_addressation_id:
                domain.append(('res_model_address_1', '=', self.cbo_id._name))
                domain.append(('first_addressation_id', '=', self.cbo_id.id))

        executors = self.env['business.role.executor'].search(domain)

        # Шукаємо найновіші записи для кожного користувача
        user_executors = []
        for user in executors.mapped('user_id'):
            latest_executor = executors.filtered(
                lambda e: e.user_id == user
            ).sorted('date', reverse=True)[:1]

            if latest_executor and latest_executor.status_role:
                user_executors.append(user.id)

        return self.env['res.users'].browse(user_executors)

    # ==================================================
    # АВТОМАТИЧНЕ ПРИЗНАЧЕННЯ РОЛЕЙ
    # ==================================================

    @api.onchange('cbo_id', 'budget_type_id')
    def _onchange_cbo_budget_type_roles(self):
        """Автоматичне призначення ролей при зміні ЦБО або типу бюджету"""
        if self.cbo_id and self.use_role_based_approval:
            self._auto_assign_budget_roles()

    def _auto_assign_budget_roles(self):
        """Автоматичне призначення бізнес-ролей для бюджету"""
        role_catalog = self.env['business.role.catalog']

        # Шукаємо стандартні ролі для бюджетування
        if not self.budget_creator_role_id:
            creator_role = role_catalog.search([
                ('role', 'ilike', 'складач'),
                ('role', 'ilike', 'бюджет')
            ], limit=1)
            self.budget_creator_role_id = creator_role.id

        if not self.budget_reviewer_role_id:
            reviewer_role = role_catalog.search([
                '|',
                ('role', 'ilike', 'перевір'),
                ('role', 'ilike', 'контрол'),
                ('role', 'ilike', 'бюджет')
            ], limit=1)
            self.budget_reviewer_role_id = reviewer_role.id

        if not self.budget_approver_role_id:
            approver_role = role_catalog.search([
                '|',
                ('role', 'ilike', 'затвердж'),
                ('role', 'ilike', 'директор'),
                ('role', 'ilike', 'бюджет')
            ], limit=1)
            self.budget_approver_role_id = approver_role.id

        # Встановлюємо адресацію
        self.role_addressing_id_1 = self.cbo_id.id

    # ==================================================
    # ІНТЕГРАЦІЯ З ПРОЦЕСОМ ЗАТВЕРДЖЕННЯ
    # ==================================================

    def action_send_coordination(self):
        """Розширена відправка на узгодження з перевіркою ролей"""
        if self.use_role_based_approval:
            self._validate_role_executors()

        # Викликаємо батьківський метод
        super().action_send_coordination()

        # Відправляємо сповіщення виконавцям ролей
        if self.use_role_based_approval:
            self._notify_role_executors('coordination_request')

    def action_approve(self):
        """Розширене затвердження з перевіркою прав ролі"""
        if self.use_role_based_approval:
            self._check_user_role_permissions('approve')

        # Викликаємо батьківський метод
        super().action_approve()

        # Відправляємо сповіщення
        if self.use_role_based_approval:
            self._notify_role_executors('approved')

    def action_request_revision(self):
        """Розширена відправка на доопрацювання"""
        if self.use_role_based_approval:
            self._check_user_role_permissions('revision')

        # Викликаємо батьківський метод
        super().action_request_revision()

        # Сповіщення
        if self.use_role_based_approval:
            self._notify_role_executors('revision_request')

    # ==================================================
    # ДОПОМІЖНІ МЕТОДИ
    # ==================================================

    def _validate_role_executors(self):
        """Перевірка наявності виконавців для всіх ролей"""
        errors = []

        if not self.current_pereviriauch_ids:
            errors.append('Не знайдено виконавців ролі "Перевіряючий бюджету"')

        if not self.current_zatverdzhuiuch_ids:
            errors.append('Не знайдено виконавців ролі "Затверджуючий бюджету"')

        if errors:
            raise ValidationError('\n'.join(errors))

    def _check_user_role_permissions(self, action):
        """Перевірка прав поточного користувача для виконання дії"""
        current_user = self.env.user

        if action in ['approve']:
            def _validate_role_executors(self):

                """Перевірка наявності виконавців для всіх ролей"""
        errors = []

        if not self.current_reviewer_ids:
            errors.append('Не знайдено виконавців ролі "Перевіряючий бюджету"')

        if not self.current_approver_ids:
            errors.append('Не знайдено виконавців ролі "Затверджуючий бюджету"')

        if errors:
            raise ValidationError('\n'.join(errors))

    def _check_user_role_permissions(self, action):
        """Перевірка прав поточного користувача для виконання дії"""
        current_user = self.env.user

        if action in ['approve']:
            if current_user not in self.current_approver_ids:
                raise UserError(
                    f'Користувач {current_user.name} не має прав для затвердження цього бюджету. '
                    f'Необхідна роль: {self.budget_approver_role_id.role}'
                )

        elif action in ['revision']:
            if current_user not in self.current_reviewer_ids and current_user not in self.current_approver_ids:
                raise UserError(
                    f'Користувач {current_user.name} не має прав для відправки бюджету на доопрацювання. '
                    f'Необхідні ролі: {self.budget_reviewer_role_id.role} або {self.budget_approver_role_id.role}'
                )

    def _notify_role_executors(self, notification_type):
        """Відправка сповіщень виконавцям ролей"""
        if notification_type == 'coordination_request':
            # Сповіщення перевіряючих
            for user in self.current_reviewer_ids:
                self.activity_schedule(
                    'mail.mail_activity_data_todo',
                    user_id=user.id,
                    summary=f'Перевірка бюджету: {self.display_name}',
                    note=f'Надійшов новий бюджет для перевірки від {self.responsible_user_id.name}'
                )

        elif notification_type == 'approved':
            # Сповіщення відповідального
            if self.responsible_user_id:
                self.activity_schedule(
                    'mail.mail_activity_data_todo',
                    user_id=self.responsible_user_id.id,
                    summary=f'Бюджет затверджено: {self.display_name}',
                    note=f'Ваш бюджет затверджено користувачем {self.env.user.name}'
                )

        elif notification_type == 'revision_request':
            # Сповіщення відповідального про доопрацювання
            if self.responsible_user_id:
                self.activity_schedule(
                    'mail.mail_activity_data_todo',
                    user_id=self.responsible_user_id.id,
                    summary=f'Бюджет потребує доопрацювання: {self.display_name}',
                    note=f'Бюджет відправлено на доопрацювання користувачем {self.env.user.name}'
                )