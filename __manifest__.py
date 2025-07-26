# -*- coding: utf-8 -*-
{
    'name': 'Система бюджетування',
    'version': '17.0.2.3.4',
    'category': 'Accounting/Management',
    'summary': 'Гнучка система бюджетування з багаторівневою структурою ЦБО, категоріями витрат та інтеграцією з прогнозами продажів',
    'description': """

                                      Система бюджетування для групи компаній "Хлебодар"

                                      Оновлена функціональність v2.3.4:
                                      * ВИПРАВЛЕНО ДЛЯ ODOO 17 EE - повна сумісність
                                      * Усунено використання attrs та інші застарілі атрибути
                                      * Оновлено JavaScript widgets до OWL framework
                                      * Виправлено CSS стилі для нового інтерфейсу
                                      * Система категорій бюджетних витрат (замість прямих рахунків)
                                      * Центри витрат для спрощеної аналітики  
                                      * Автоматичне зіставлення категорій з обліковими рахунками
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
        # 1. БЕЗПЕКА (ЗАВЖДИ ПЕРШОЮ!)
        'security/budget_security.xml',
        'security/ir.model.access.csv',

        # 2. БАЗОВІ МОДЕЛІ та КОНФІГУРАЦІЯ
        'views/budget_config_views.xml',
        'views/budget_period_views.xml',
        'views/budget_type_views.xml',
        'views/budget_category_views.xml',

        # 3. ОСНОВНІ VIEWS МОДЕЛЕЙ
        'views/budget_plan_views.xml',
        'views/sales_forecast_views.xml',
        'views/budget_execution_views.xml',

        # 4. СПЕЦІАЛІЗОВАНІ VIEWS ДЛЯ ДЕРЕВА
        'views/hierarchy_tree_views.xml',
        'views/tree_dashboard_views.xml',
        'views/tree_simple_dashboard.xml',
        'views/tree_advanced_views.xml',

        # 5. WIZARDS та ІНСТРУМЕНТИ
        'wizard/budget_wizard_views.xml',
        'wizard/sales_forecast_wizard_views.xml',
        'wizard/budget_import_wizard_views.xml',
        'wizard/budget_approval_wizard_views.xml',

        # 6. МЕНЮ (базова структура) - ПІСЛЯ ВСІХ ДІЙ
        'views/menu_structure.xml',
        'views/menu_actions.xml',

        # 7. ЗВІТИ
        'report/budget_report_templates.xml',

        # 8. БАЗОВІ ДАНІ (після всіх представлень і wizards)
        'data/budget_types_data.xml',
        'data/server_actions_budget_types.xml',
        'data/responsibility_centers_data.xml',
        'data/budget_categories_demo_data.xml',
        'data/server_actions_categories.xml',
        'data/bdr_categories_data.xml',

        # 9. ШАБЛОНИ ПОШТИ та АВТОМАТИЗАЦІЯ (наприкінці)
        'data/mail_template_data.xml',
        'data/ir_cron_data.xml',
    ],
    'demo': [
        'demo/budget_demo_data.xml',
    ],
    'assets': {
        # ОСНОВНІ ASSETS ДЛЯ BACKEND (ODOO 17 ФОРМАТ)
        'web.assets_backend': [
            # CSS файли - порядок важливий!
            'budget/static/src/css/tree_simple.css',
            'budget/static/src/css/hierarchy_tree.css',
            'budget/static/src/css/budget_dashboard.css',

            # JavaScript файли - СУМІСНІ З OWL (Odoo 17)
            'budget/static/src/js/budget_widgets.js',
            'budget/static/src/js/hierarchy_tree_widget.js',
            'budget/static/src/js/tree_advanced_widget.js',
        ],

        # ASSETS ДЛЯ FRONTEND (якщо потрібен портал)
        'web.assets_frontend': [
            'budget/static/src/css/budget_portal.css',
            'budget/static/src/css/budget_compact.css',
            'budget/static/src/css/hierarchy_tree.css',
            'budget/static/src/css/tree_simple.css',
        ],

        # ASSETS ДЛЯ ЗВІТІВ PDF
        'web.report_assets_common': [
            'budget/static/src/css/budget_reports.css',
        ],

        # XML ШАБЛОНИ ДЛЯ OWL КОМПОНЕНТІВ (Odoo 17)
        'web.assets_qweb': [
            'budget/static/src/xml/tree_templates.xml',
        ],
    },
    'external_dependencies': {
        'python': ['xlsxwriter', 'openpyxl'],
    },
    'installable': True,
    'auto_install': False,
    'application': True,
    'sequence': 45,

    # НАЛАШТУВАННЯ ДЛЯ ODOO 17
    'post_init_hook': 'budget.hooks._post_init_hook',
    'uninstall_hook': 'budget.hooks._uninstall_hook',

    # МІНІМАЛЬНА ВЕРСІЯ
    'odoo_version': '17.0',

    # КОНФІГУРАЦІЯ МОДУЛЯ
    'web': True,
    'bootstrap': True,
}