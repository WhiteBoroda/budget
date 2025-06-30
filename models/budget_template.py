# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import UserError


class BudgetTemplate(models.Model):
    """Шаблоны бюджетов для стандартизации процесса"""
    _name = 'budget.template'
    _description = 'Шаблон бюджета'
    _order = 'budget_type_id, cbo_type, name'

    name = fields.Char('Название шаблона', required=True)
    description = fields.Text('Описание')

    # Привязка к типу бюджета и ЦБО
    budget_type_id = fields.Many2one('budget.type', 'Тип бюджета', required=True)
    cbo_type = fields.Selection([
        ('holding', 'Холдинг'),
        ('cluster', 'Кластер'),
        ('business_direction', 'Направление бизнеса'),
        ('brand', 'Бренд'),
        ('enterprise', 'Предприятие'),
        ('department', 'Департамент'),
        ('division', 'Управление'),
        ('office', 'Отдел'),
        ('team', 'Группа/Команда'),
        ('project', 'Проект'),
        ('other', 'Другое')
    ], 'Тип ЦБО', help="Для каких ЦБО применим этот шаблон")

    # Настройки применения
    applicable_cbo_ids = fields.Many2many('budget.responsibility.center',
                                          string='Применимые ЦБО')
    is_default = fields.Boolean('Шаблон по умолчанию',
                                help="Автоматически предлагается при создании бюджета")

    # Линии шаблона
    line_ids = fields.One2many('budget.template.line', 'template_id', 'Позиции шаблона')

    # Статистика использования
    usage_count = fields.Integer('Количество использований', compute='_compute_usage_stats')
    last_used_date = fields.Datetime('Последнее использование', compute='_compute_usage_stats')

    # Настройки автоматизации
    auto_calculation = fields.Boolean('Автоматический расчет',
                                      help="Автоматически рассчитывать суммы при создании бюджета")
    growth_rate = fields.Float('Коэффициент роста по умолчанию, %',
                               help="Применяется при копировании из предыдущего периода")

    active = fields.Boolean('Активный', default=True)
    company_id = fields.Many2one('res.company', 'Компания', default=lambda self: self.env.company)

    @api.depends('line_ids')
    def _compute_usage_stats(self):
        """Подсчет статистики использования шаблона"""
        for template in self:
            # Ищем бюджеты, созданные по этому шаблону
            budgets = self.env['budget.plan'].search([
                ('notes', 'ilike', f'шаблон {template.id}')
            ])
            template.usage_count = len(budgets)
            template.last_used_date = max(budgets.mapped('create_date')) if budgets else False

    def action_create_budget_from_template(self):
        """Создание бюджета на основе шаблона"""
        return {
            'type': 'ir.actions.act_window',
            'name': 'Создать бюджет из шаблона',
            'res_model': 'budget.template.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_template_id': self.id,
                'default_budget_type_id': self.budget_type_id.id,
            }
        }

    def action_update_from_budget(self):
        """Обновление шаблона на основе существующего бюджета"""
        return {
            'type': 'ir.actions.act_window',
            'name': 'Обновить шаблон из бюджета',
            'res_model': 'budget.template.update.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_template_id': self.id,
            }
        }

    def copy_from_budget(self, budget_plan):
        """Копирование позиций из существующего бюджета"""
        # Очищаем существующие линии
        self.line_ids.unlink()

        # Создаем новые линии на основе бюджета
        for line in budget_plan.line_ids:
            self.env['budget.template.line'].create({
                'template_id': self.id,
                'description': line.description,
                'account_id': line.account_id.id if line.account_id else False,
                'default_quantity': line.quantity,
                'default_unit_price': line.unit_price,
                'calculation_method': line.calculation_method,
                'calculation_formula': line.calculation_basis,
                'sequence': len(self.line_ids) + 1,
            })


class BudgetTemplateLine(models.Model):
    """Позиции шаблона бюджета"""
    _name = 'budget.template.line'
    _description = 'Позиция шаблона бюджета'
    _order = 'sequence, id'

    template_id = fields.Many2one('budget.template', 'Шаблон', required=True, ondelete='cascade')
    sequence = fields.Integer('Последовательность', default=10)

    # Основные поля
    description = fields.Char('Описание', required=True)
    account_id = fields.Many2one('account.account', 'Счет')
    analytic_account_id = fields.Many2one('account.analytic.account', 'Аналитический счет')

    # Значения по умолчанию
    default_quantity = fields.Float('Количество по умолчанию', default=1.0)
    default_unit_price = fields.Float('Цена по умолчанию')

    # Настройки расчета
    calculation_method = fields.Selection([
        ('manual', 'Ручной ввод'),
        ('formula', 'По формуле'),
        ('previous_period', 'Из предыдущего периода'),
        ('percentage', 'Процент от базы'),
        ('norm_based', 'По нормативам'),
    ], 'Метод расчета', default='manual')

    calculation_formula = fields.Text('Формула расчета',
                                      help="Например: quantity * price * 1.2")
    percentage_base = fields.Float('Процент от базы')

    # Дополнительные параметры
    is_mandatory = fields.Boolean('Обязательная позиция', default=True)
    allow_edit = fields.Boolean('Разрешить редактирование', default=True)

    notes = fields.Text('Примечания')


class BudgetTemplateWizard(models.TransientModel):
    """Мастер создания бюджета из шаблона"""
    _name = 'budget.template.wizard'
    _description = 'Создание бюджета из шаблона'

    template_id = fields.Many2one('budget.template', 'Шаблон', required=True)
    period_id = fields.Many2one('budget.period', 'Период', required=True)
    cbo_id = fields.Many2one('budget.responsibility.center', 'ЦБО', required=True)
    budget_type_id = fields.Many2one('budget.type', 'Тип бюджета', required=True)

    # Настройки применения шаблона
    copy_from_previous = fields.Boolean('Копировать суммы из предыдущего периода')
    previous_period_id = fields.Many2one('budget.period', 'Предыдущий период')
    growth_rate = fields.Float('Коэффициент роста, %', default=0.0)

    # Дополнительные настройки
    responsible_user_id = fields.Many2one('res.users', 'Ответственный',
                                          default=lambda self: self.env.user)
    company_id = fields.Many2one('res.company', 'Компания',
                                 default=lambda self: self.env.company)

    @api.onchange('template_id')
    def _onchange_template_id(self):
        """Автозаполнение при выборе шаблона"""
        if self.template_id:
            self.budget_type_id = self.template_id.budget_type_id
            self.growth_rate = self.template_id.growth_rate

    @api.onchange('period_id')
    def _onchange_period_id(self):
        """Поиск предыдущего периода"""
        if self.period_id:
            previous = self.env['budget.period'].search([
                ('date_end', '<', self.period_id.date_start),
                ('company_id', '=', self.company_id.id)
            ], order='date_end desc', limit=1)
            self.previous_period_id = previous.id if previous else False

    def action_create_budget(self):
        """Создание бюджета по шаблону"""
        # Проверяем, не существует ли уже такой бюджет
        existing = self.env['budget.plan'].search([
            ('period_id', '=', self.period_id.id),
            ('cbo_id', '=', self.cbo_id.id),
            ('budget_type_id', '=', self.budget_type_id.id)
        ])

        if existing:
            raise UserError(f'Бюджет уже существует: {existing.display_name}')

        # Создаем бюджет
        budget = self.env['budget.plan'].create({
            'period_id': self.period_id.id,
            'cbo_id': self.cbo_id.id,
            'budget_type_id': self.budget_type_id.id,
            'company_id': self.company_id.id,
            'responsible_user_id': self.responsible_user_id.id,
            'state': 'draft',
            'notes': f'Создано из шаблона {self.template_id.name} (ID: {self.template_id.id})'
        })

        # Создаем линии из шаблона
        for template_line in self.template_id.line_ids:
            line_vals = self._prepare_budget_line_vals(budget, template_line)
            self.env['budget.plan.line'].create(line_vals)

        return {
            'type': 'ir.actions.act_window',
            'name': 'Созданный бюджет',
            'res_model': 'budget.plan',
            'res_id': budget.id,
            'view_mode': 'form',
            'target': 'current'
        }

    def _prepare_budget_line_vals(self, budget, template_line):
        """Подготовка значений для строки бюджета"""
        # Базовые значения из шаблона
        quantity = template_line.default_quantity
        unit_price = template_line.default_unit_price

        # Если нужно копировать из предыдущего периода
        if self.copy_from_previous and self.previous_period_id:
            previous_amount = self._get_previous_amount(template_line)
            if previous_amount:
                growth_factor = 1 + (self.growth_rate / 100)
                unit_price = previous_amount * growth_factor

        # Рассчитываем сумму
        planned_amount = quantity * unit_price

        return {
            'plan_id': budget.id,
            'description': template_line.description,
            'account_id': template_line.account_id.id if template_line.account_id else False,
            'analytic_account_id': template_line.analytic_account_id.id if template_line.analytic_account_id else False,
            'quantity': quantity,
            'unit_price': unit_price,
            'planned_amount': planned_amount,
            'calculation_method': template_line.calculation_method,
            'calculation_basis': f'Шаблон: {template_line.calculation_formula or "стандартный расчет"}',
            'notes': template_line.notes,
        }

    def _get_previous_amount(self, template_line):
        """Получение суммы из предыдущего периода"""
        previous_budget = self.env['budget.plan'].search([
            ('period_id', '=', self.previous_period_id.id),
            ('cbo_id', '=', self.cbo_id.id),
            ('budget_type_id', '=', self.budget_type_id.id),
            ('state', '=', 'approved')
        ], limit=1)

        if not previous_budget:
            return 0.0

        # Ищем похожую строку в предыдущем бюджете
        similar_line = previous_budget.line_ids.filtered(
            lambda l: l.description == template_line.description or
                      l.account_id == template_line.account_id
        )

        return similar_line[0].planned_amount if similar_line else 0.0


class BudgetTemplateUpdateWizard(models.TransientModel):
    """Мастер обновления шаблона из бюджета"""
    _name = 'budget.template.update.wizard'
    _description = 'Обновление шаблона из бюджета'

    template_id = fields.Many2one('budget.template', 'Шаблон', required=True)
    budget_plan_id = fields.Many2one('budget.plan', 'Бюджет-источник', required=True)
    update_mode = fields.Selection([
        ('replace', 'Заменить все позиции'),
        ('merge', 'Объединить с существующими'),
        ('add_new', 'Добавить только новые')
    ], 'Режим обновления', default='replace')

    def action_update_template(self):
        """Обновление шаблона"""
        if self.update_mode == 'replace':
            self.template_id.line_ids.unlink()

        for line in self.budget_plan_id.line_ids:
            # Проверяем, есть ли уже такая позиция
            existing = self.template_id.line_ids.filtered(
                lambda l: l.description == line.description
            )

            if existing and self.update_mode == 'add_new':
                continue  # Пропускаем существующие
            elif existing and self.update_mode == 'merge':
                # Обновляем существующую
                existing.write({
                    'default_quantity': line.quantity,
                    'default_unit_price': line.unit_price,
                    'account_id': line.account_id.id if line.account_id else False,
                })
            else:
                # Создаем новую
                self.env['budget.template.line'].create({
                    'template_id': self.template_id.id,
                    'description': line.description,
                    'account_id': line.account_id.id if line.account_id else False,
                    'default_quantity': line.quantity,
                    'default_unit_price': line.unit_price,
                    'calculation_method': line.calculation_method,
                    'sequence': len(self.template_id.line_ids) + 1,
                })

        return {'type': 'ir.actions.act_window_close'}