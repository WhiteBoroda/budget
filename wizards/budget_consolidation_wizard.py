# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class BudgetConsolidationWizard(models.TransientModel):
    """Wizard для створення структури консолідації"""
    _name = 'budget.consolidation.wizard'
    _description = 'Майстер створення консолідації бюджетів'

    # Основні параметри
    period_id = fields.Many2one('budget.period', 'Період', required=True)
    budget_type_id = fields.Many2one('budget.type', 'Тип бюджету', required=True)

    # Рівні створення
    create_holding_budgets = fields.Boolean('Створювати бюджети холдингу', default=True)
    create_company_budgets = fields.Boolean('Створювати бюджети компаній', default=True)
    create_site_budgets = fields.Boolean('Створювати бюджети площадок', default=True)
    create_for_all_levels = fields.Boolean('Для всіх рівнів ЦБО', default=True)

    # Налаштування
    auto_consolidate_enabled = fields.Boolean('Увімкнути автоконсолідацію', default=True)
    copy_from_previous_period = fields.Boolean('Копіювати з попереднього періоду', default=False)
    send_notifications = fields.Boolean('Відправити сповіщення відповідальним', default=True)

    # Попередній перегляд
    preview_structure = fields.Text('Попередній перегляд структури', readonly=True)

    def action_preview_structure(self):
        """Попередній перегляд структури консолідації"""
        structure_info = self._analyze_consolidation_structure()

        preview_text = f"""
🏗️ СТРУКТУРА КОНСОЛІДАЦІЇ

📅 Період: {self.period_id.name}
📂 Тип бюджету: {self.budget_type_id.name}

📊 СТАТИСТИКА:
• Холдингових ЦБО: {structure_info['holding_count']}
• Компанійних ЦБО: {structure_info['company_count']}  
• Площадкових ЦБО: {structure_info['site_count']}
• Загалом бюджетів буде створено: {structure_info['total_budgets']}

🏢 СТРУКТУРА ХОЛДИНГУ:
{structure_info['structure_tree']}

⚙️ НАЛАШТУВАННЯ:
• Автоконсолідація: {'✅ Увімкнена' if self.auto_consolidate_enabled else '❌ Вимкнена'}
• Копіювання з попереднього періоду: {'✅ Так' if self.copy_from_previous_period else '❌ Ні'}
• Сповіщення: {'✅ Будуть відправлені' if self.send_notifications else '❌ Не будуть'}

🎯 ГОТОВИЙ ДО СТВОРЕННЯ!
        """

        self.preview_structure = preview_text

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'budget.consolidation.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'context': {'preview_done': True}
        }

    def action_create_structure(self):
        """Створення всієї структури консолідації"""
        created_budgets = self.env['budget.plan'].create_consolidation_structure(
            self.period_id.id,
            self.budget_type_id.id
        )

        if not created_budgets:
            raise UserError('Не вдалося створити структуру бюджетів. Перевірте налаштування ЦБО.')

        # Налаштовуємо автоконсолідацію
        if self.auto_consolidate_enabled:
            for budget in created_budgets.values():
                budget.auto_consolidate = True

        # Копіюємо дані з попереднього періоду
        if self.copy_from_previous_period:
            self._copy_from_previous_period(created_budgets)

        # Відправляємо сповіщення
        if self.send_notifications:
            self._send_notifications(created_budgets)

        # Результат
        result_message = f"""
✅ СТРУКТУРА КОНСОЛІДАЦІЇ СТВОРЕНА!

📊 Створено бюджетів: {len(created_budgets)}
📅 Період: {self.period_id.name}
📂 Тип: {self.budget_type_id.name}

🎯 Наступні кроки:
1. Заповніть бюджети площадок
2. Система автоматично консолідує дані вгору
3. Перевірте та затвердіть консолідовані бюджети
        """

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Структура створена!',
                'message': result_message,
                'type': 'success',
                'sticky': True,
                'next': {
                    'type': 'ir.actions.act_window',
                    'name': 'Створені бюджети',
                    'res_model': 'budget.plan',
                    'view_mode': 'tree,form',
                    'domain': [('id', 'in', list(created_budgets.values()))],
                    'context': {'group_by': ['consolidation_level', 'cbo_id']}
                }
            }
        }

    def _analyze_consolidation_structure(self):
        """Аналіз структури для попереднього перегляду"""
        cbo_obj = self.env['budget.responsibility.center']

        # Підрахунок ЦБО по рівнях
        holding_cbos = cbo_obj.search([('cbo_type', '=', 'holding')])
        company_cbos = cbo_obj.search([('cbo_type', 'in', ['enterprise', 'business_direction'])])
        site_cbos = cbo_obj.search([('cbo_type', 'in', ['department', 'division', 'office'])])

        total_budgets = 0
        if self.create_holding_budgets:
            total_budgets += len(holding_cbos)
        if self.create_company_budgets:
            total_budgets += len(company_cbos)
        if self.create_site_budgets:
            total_budgets += len(site_cbos)

        # Створення дерева структури
        structure_tree = ""
        for holding in holding_cbos:
            structure_tree += f"🏢 {holding.name}\n"

            companies = cbo_obj.search([('parent_id', '=', holding.id)])
            for company in companies:
                structure_tree += f"  ├── 🏭 {company.name}\n"

                sites = cbo_obj.search([('parent_id', '=', company.id)])
                for i, site in enumerate(sites):
                    prefix = "  │   └──" if i == len(sites) - 1 else "  │   ├──"
                    structure_tree += f"{prefix} 🏪 {site.name}\n"

        return {
            'holding_count': len(holding_cbos),
            'company_count': len(company_cbos),
            'site_count': len(site_cbos),
            'total_budgets': total_budgets,
            'structure_tree': structure_tree or "❌ Структура ЦБО не налаштована"
        }

    def _copy_from_previous_period(self, created_budgets):
        """Копіювання даних з попереднього періоду"""
        copy_wizard_obj = self.env['budget.copy.wizard']

        for cbo_id, budget in created_budgets.items():
            # Шукаємо попередній бюджет того ж типу та ЦБО
            previous_budget = self.env['budget.plan'].search([
                ('cbo_id', '=', cbo_id),
                ('budget_type_id', '=', self.budget_type_id.id),
                ('period_id.date_end', '<', self.period_id.date_start)
            ], order='period_id desc', limit=1)

            if previous_budget:
                # Створюємо wizard копіювання
                copy_wizard = copy_wizard_obj.create({
                    'target_budget_id': budget.id,
                    'copy_mode': 'another_budget',
                    'source_budget_id': previous_budget.id,
                    'copy_amounts': True,
                    'copy_categories': True,
                    'copy_descriptions': True,
                    'amount_adjustment_type': 'none'
                })

                # Виконуємо копіювання
                copy_wizard.action_execute_copy()

    def _send_notifications(self, created_budgets):
        """Відправка сповіщень відповідальним за бюджети"""
        for budget in created_budgets.values():
            if budget.responsible_user_id:
                budget.activity_schedule(
                    'mail.mail_activity_data_todo',
                    user_id=budget.responsible_user_id.id,
                    summary=f'Новий бюджет для планування: {budget.name}',
                    note=f"""
Створено новий бюджет для планування:

📋 Назва: {budget.name}
📅 Період: {budget.period_id.name}
🏢 ЦБО: {budget.cbo_id.name}
📂 Тип: {budget.budget_type_id.name}

Будь ласка, заповніть планові показники та відправте на затвердження.
                    """
                )

                budget.message_post(
                    body=f"Бюджет призначено відповідальному: {budget.responsible_user_id.name}",
                    subject="Призначення відповідального",
                    partner_ids=[budget.responsible_user_id.partner_id.id]
                )