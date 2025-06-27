# -*- coding: utf-8 -*-
{
    'name': 'Система бюджетування ГК Хлебодар',
    'version': '17.0.1.0.3',
    'category': 'Accounting/Management',
    'summary': 'Комплексна система бюджетування з трирівневою структурою',
    'description': """
Система бюджетування для групи компаній "Хлебодар"

Функціонал:
* Трирівнева структура бюджетування (ЦБО, ПП, Консолідований)
* Формування планів продажів
* 32 типи бюджетів згідно регламенту
* Матрична структура відповідальності
* Автоматизація процесів узгодження
* Звітність та аналітика
""",
    'author': 'HD Digital Solution',
    'website': 'https://hd-group.ua',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'account',
        'sale',
        'purchase',
        'hr',
        'project',
        'stock',
        'mail'
    ],
    'data': [
        # 1. БЕЗПЕКА (завжди першою)
        'security/budget_security.xml',
        'security/ir.model.access.csv',

        # 2. ПОСЛІДОВНОСТІ (потрібні для моделей)
        'data/ir_sequence_data.xml',

        # 3. МЕНЮ (базова структура)
        'views/menu_views.xml',

        # 4. ОСНОВНІ ПРЕДСТАВЛЕННЯ МОДЕЛЕЙ
        'views/budget_config_views.xml',
        'views/sales_plan_views.xml',
        'views/budget_plan_views.xml',
        'views/budget_execution_views.xml',
        'views/budget_dashboard_views.xml',
        'views/budget_analysis_views.xml',
        'views/budget_notification_views.xml',
        'views/budget_reports_views.xml',
        'views/budget_help_views.xml',
        'views/budget_quick_actions.xml',

        # 5. WIZARDS (після основних представлень)
        'wizards/budget_approval_wizard_views.xml',
        'wizards/budget_consolidation_wizard_views.xml',
        'wizards/sales_plan_wizard_views.xml',
        'wizards/budget_period_wizard_views.xml',

        # 6. ЗВІТИ
        'report/budget_report_templates.xml',

        # 7. БАЗОВІ ДАНІ (після всіх представлень і wizards)
        'data/budget_types_data.xml',
        'data/responsibility_centers_data.xml',  # ВКЛЮЧАЕМ ОБРАТНО

        # 8. ШАБЛОНИ ПОШТИ та АВТОМАТИЗАЦІЯ (наприкінці)
        'data/mail_template_data.xml',
        'data/ir_cron_data.xml',
    ],
    'demo': [
        'demo/budget_demo_data.xml',
    ],
    'qweb': [],
    'installable': True,
    'auto_install': False,
    'application': True,
    'sequence': 45,
}