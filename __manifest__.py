# -*- coding: utf-8 -*-
{
    'name': 'Система бюджетування',
    'version': '17.0.2.3.2',
    'category': 'Accounting/Management',
    'summary': 'Гнучка система бюджетування з багаторівневою структурою ЦБО, категоріями витрат та інтеграцією з прогнозами продажів',
    'description': """
Система бюджетування для групи компаній "Хлебодар"

Оновлена функціональність v2.3.2:
* Система категорій бюджетних витрат (замість прямих рахунків)
* Центри витрат для спрощеної аналітики  
* Автоматичне зопоставлення категорій з обліковими рахунками
* Масове призначення категорій через wizard
* Автоматичне визначення категорій по ключових словах
* Шаблони бюджетів з категоріями
* Спрощений інтерфейс для звичайних користувачів
* Розширений інтерфейс для бухгалтерів та адміністраторів
* Гнучка структура ЦБО (кластери, напрямки, бренди, департаменти)
* Інтеграція з модулем Sales через прогнози продажів
* Багаторівнева система бюджетування
* Автоматична консолідація бюджетів
* Розширені можливості планування та контролю
* Валютні налаштування для міжнародного бізнесу
* Виправлено для Odoo 17 EE
""",
    'author': 'HD Digital Solution',
    'website': 'https://hd-group.ua',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'web',
        'account',
        'sale',
        'sale_management',
        'crm',
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
        'security/ir.model.access_categories.csv',  # ДОДАНО: права для категорій

        # 2. ПОСЛІДОВНОСТІ (потрібні для моделей)
        'data/ir_sequence_data.xml',

        # 4. ОСНОВНІ ПРЕДСТАВЛЕННЯ МОДЕЛЕЙ
        'views/budget_config_views.xml',
        'views/budget_category_views.xml',  # ДОДАНО: категорії витрат
        'views/sales_forecast_views.xml',
        'views/crm_team_views.xml',
        'views/project_views.xml',
        'views/budget_plan_views.xml',
        'views/budget_plan_view_cat.xml',  # ДОДАНО: представлення з категоріями
        'views/budget_execution_views.xml',
        'views/budget_dashboard_views.xml',
        'views/budget_analysis_views.xml',
        'views/budget_notification_views.xml',
        'views/investment_budget_views.xml',
        'views/budget_reports_views.xml',
        'views/budget_template_views.xml',
        'views/forecast_analysis_views.xml',
        'views/budget_categories_reports.xml',  # ДОДАНО: звіти по категоріях
        'views/budget_help_views.xml',
        'views/budget_quick_actions.xml',
        'data/bdr_categories_data.xml',

        # 5. WIZARDS (після основних представлень)
        'wizards/budget_approval_wizard_views.xml',
        'wizards/budget_consolidation_wizard_views.xml',
        'wizards/budget_import_wizard_views.xml',
        'wizards/sales_plan_wizard_views.xml',
        'wizards/budget_period_wizard_views.xml',
        'wizards/budget_assign_categories_wizard_views.xml',  # ДОДАНО: wizard категорій
        'wizards/bdr_budget_wizard_views.xml',
        'wizards/bdr_budget_wizard_enhanced_views.xml',
        'wizards/budget_category_manager_wizard_views.xml',



        # 3. МЕНЮ (базова структура) - ПЕРЕНЕСЕНО СЮДИ, ПІСЛЯ ВСІХ ДІЙ
        'views/menu_views.xml',

        # 6. ЗВІТИ
        'report/budget_report_templates.xml',

        # 7. БАЗОВІ ДАНІ (після всіх представлень і wizards)
        'data/budget_types_data.xml',
        'data/server_actions_budget_types.xml',
        'data/responsibility_centers_data.xml',
        'data/budget_categories_demo_data.xml',  # ДОДАНО: демо категорії витрат
        'data/server_actions_categories.xml',  # ДОДАНО: server actions для категорій

        # 8. ШАБЛОНИ ПОШТИ та АВТОМАТИЗАЦІЯ (наприкінці)
        'data/mail_template_data.xml',
        'data/ir_cron_data.xml',
    ],
    'demo': [
        'demo/budget_demo_data.xml',
    ],
    'assets': {
        # Основные стили для backend (админки)
        'web.assets_backend': [
            'budget/static/src/css/budget_dashboard.css',
            'budget/static/src/js/budget_widgets.js',
        ],
        # Стили для frontend (портала) - если планируется портальная часть
        'web.assets_frontend': [
            'budget/static/src/css/budget_portal.css',
        ],
        # Дополнительно: стили для отчетов PDF
        'web.report_assets_common': [
            'budget/static/src/css/budget_reports.css',
        ],
    },
    'qweb': [],
    'installable': True,
    'auto_install': False,
    'application': True,
    'sequence': 45,
}