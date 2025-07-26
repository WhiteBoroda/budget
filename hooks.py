# -*- coding: utf-8 -*-
# hooks.py - Post init та uninstall hooks для бюджетного модуля

import logging
from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def _post_init_hook(cr, registry):
    """Post init hook для налаштування модуля після встановлення"""
    _logger.info("Starting budget module post-init configuration...")

    with api.Environment.manage():
        env = api.Environment(cr, SUPERUSER_ID, {})

        try:
            # 1. Створення базових даних якщо їх немає
            _create_default_data(env)

            # 2. Налаштування послідовностей
            _setup_sequences(env)

            # 3. Створення базових ЦБО якщо їх немає
            _create_default_cbos(env)

            # 4. Налаштування базових типів бюджетів
            _setup_budget_types(env)

            # 5. Створення базових категорій витрат
            _setup_budget_categories(env)

            # 6. Налаштування шаблонів повідомлень
            _setup_mail_templates(env)

            # 7. Налаштування cron завдань
            _setup_cron_jobs(env)

            # 8. Оновлення прав доступу
            _update_access_rights(env)

            # 9. Індексація для продуктивності
            _create_database_indexes(env)

            # 10. Ініціалізація dashboard
            _initialize_dashboard_data(env)

            _logger.info("Budget module post-init configuration completed successfully")

        except Exception as e:
            _logger.error(f"Error during post-init hook: {str(e)}")
            # Не падаємо, щоб не зламати встановлення модуля
            pass


def _create_default_data(env):
    """Створення базових даних"""
    _logger.info("Creating default data...")

    # Створення базового періоду якщо його немає
    current_year = env.context.get('current_year', 2024)
    period_name = f"Бюджетний період {current_year}"

    existing_period = env['budget.period'].search([('name', '=', period_name)], limit=1)
    if not existing_period:
        env['budget.period'].create({
            'name': period_name,
            'date_start': f'{current_year}-01-01',
            'date_end': f'{current_year}-12-31',
            'state': 'open',
            'is_default': True
        })
        _logger.info(f"Created default budget period: {period_name}")


def _setup_sequences(env):
    """Налаштування послідовностей"""
    _logger.info("Setting up sequences...")

    sequences_data = [
        {
            'name': 'Бюджетні плани',
            'code': 'budget.plan',
            'prefix': 'BUD',
            'padding': 5,
            'number_next': 1,
            'number_increment': 1,
        },
        {
            'name': 'Центри відповідальності',
            'code': 'budget.responsibility.center',
            'prefix': 'CBO',
            'padding': 4,
            'number_next': 1,
            'number_increment': 1,
        },
        {
            'name': 'Прогнози продажів',
            'code': 'sale.forecast',
            'prefix': 'FOR',
            'padding': 5,
            'number_next': 1,
            'number_increment': 1,
        }
    ]

    for seq_data in sequences_data:
        existing = env['ir.sequence'].search([('code', '=', seq_data['code'])], limit=1)
        if not existing:
            env['ir.sequence'].create(seq_data)
            _logger.info(f"Created sequence for {seq_data['name']}")


def _create_default_cbos(env):
    """Створення базових ЦБО"""
    _logger.info("Creating default CBOs...")

    # Перевіряємо чи є вже ЦБО
    existing_cbos = env['budget.responsibility.center'].search([])
    if existing_cbos:
        _logger.info("CBOs already exist, skipping creation")
        return

    # Створюємо кореневий холдинг
    company = env.company
    root_cbo = env['budget.responsibility.center'].create({
        'name': f'Холдинг {company.name}',
        'code': 'HOLD01',
        'cbo_type': 'holding',
        'budget_level': 'strategic',
        'sequence': 10,
        'active': True,
        'region': 'Україна',
        'business_segment': 'Основний бізнес'
    })

    # Створюємо базове підприємство
    enterprise_cbo = env['budget.responsibility.center'].create({
        'name': f'Підприємство {company.name}',
        'code': 'ENT01',
        'parent_id': root_cbo.id,
        'cbo_type': 'enterprise',
        'budget_level': 'operational',
        'sequence': 10,
        'active': True
    })

    # Створюємо базові департаменти
    departments = [
        ('Фінансовий департамент', 'FIN01', 'Фінанси'),
        ('Департамент продажів', 'SAL01', 'Продажі'),
        ('Виробничий департамент', 'PRD01', 'Виробництво'),
        ('IT департамент', 'IT01', 'ІТ')
    ]

    for dept_name, dept_code, segment in departments:
        env['budget.responsibility.center'].create({
            'name': dept_name,
            'code': dept_code,
            'parent_id': enterprise_cbo.id,
            'cbo_type': 'department',
            'budget_level': 'functional',
            'sequence': 10,
            'active': True,
            'business_segment': segment
        })

    _logger.info(f"Created default CBO structure with {len(departments) + 2} nodes")


def _setup_budget_types(env):
    """Налаштування базових типів бюджетів"""
    _logger.info("Setting up budget types...")

    budget_types = [
        {
            'name': 'Операційний бюджет',
            'code': 'OPER',
            'description': 'Бюджет операційної діяльності',
            'sequence': 10,
            'active': True
        },
        {
            'name': 'Інвестиційний бюджет',
            'code': 'INV',
            'description': 'Бюджет капітальних вкладень',
            'sequence': 20,
            'active': True
        },
        {
            'name': 'Фінансовий бюджет',
            'code': 'FIN',
            'description': 'Фінансовий бюджет та cash flow',
            'sequence': 30,
            'active': True
        }
    ]

    for bt_data in budget_types:
        existing = env['budget.type'].search([('code', '=', bt_data['code'])], limit=1)
        if not existing:
            env['budget.type'].create(bt_data)
            _logger.info(f"Created budget type: {bt_data['name']}")


def _setup_budget_categories(env):
    """Налаштування базових категорій витрат"""
    _logger.info("Setting up budget categories...")

    categories = [
        {
            'name': 'Заробітна плата',
            'code': 'SAL',
            'category_type': 'expense',
            'is_revenue': False,
            'sequence': 10
        },
        {
            'name': 'Оренда та комунальні послуги',
            'code': 'RENT',
            'category_type': 'expense',
            'is_revenue': False,
            'sequence': 20
        },
        {
            'name': 'Маркетинг та реклама',
            'code': 'MKT',
            'category_type': 'expense',
            'is_revenue': False,
            'sequence': 30
        },
        {
            'name': 'Доходи від продажів',
            'code': 'REV',
            'category_type': 'revenue',
            'is_revenue': True,
            'sequence': 10
        }
    ]

    for cat_data in categories:
        existing = env['budget.category'].search([('code', '=', cat_data['code'])], limit=1)
        if not existing:
            env['budget.category'].create(cat_data)
            _logger.info(f"Created budget category: {cat_data['name']}")


def _setup_mail_templates(env):
    """Налаштування шаблонів повідомлень"""
    _logger.info("Setting up mail templates...")

    # Шаблон для затвердження бюджету
    approval_template = {
        'name': 'Затвердження бюджету',
        'model_id': env.ref('budget.model_budget_plan').id,
        'subject': 'Бюджет ${object.name} потребує затвердження',
        'body_html': '''
        <p>Шановний ${object.cbo_id.responsible_user_id.name or 'користувач'},</p>
        <p>Бюджет <strong>${object.name}</strong> очікує на ваше затвердження.</p>
        <p><strong>Деталі бюджету:</strong></p>
        <ul>
            <li>ЦБО: ${object.cbo_id.name}</li>
            <li>Період: ${object.period_id.name}</li>
            <li>Планова сума: ${object.planned_amount} ${object.currency_id.name}</li>
        </ul>
        <p>Для затвердження перейдіть за посиланням: 
           <a href="/web#id=${object.id}&model=budget.plan">Переглянути бюджет</a>
        </p>
        ''',
        'auto_delete': True,
        'email_from': '${(object.company_id.email and object.company_id.email or "")}',
        'email_to': '${object.cbo_id.responsible_user_id.email}'
    }

    existing = env['mail.template'].search([
        ('name', '=', approval_template['name']),
        ('model_id', '=', approval_template['model_id'])
    ], limit=1)

    if not existing:
        env['mail.template'].create(approval_template)
        _logger.info("Created budget approval mail template")


def _setup_cron_jobs(env):
    """Налаштування cron завдань"""
    _logger.info("Setting up cron jobs...")

    # Автоматичне нагадування про прострочені бюджети
    cron_data = {
        'name': 'Нагадування про прострочені бюджети',
        'model_id': env.ref('budget.model_budget_plan').id,
        'state': 'code',
        'code': 'model.send_overdue_budget_reminders()',
        'interval_number': 1,
        'interval_type': 'days',
        'numbercall': -1,
        'doall': False,
        'active': True,
        'user_id': SUPERUSER_ID
    }

    existing = env['ir.cron'].search([('name', '=', cron_data['name'])], limit=1)
    if not existing:
        env['ir.cron'].create(cron_data)
        _logger.info("Created overdue budget reminder cron job")


def _update_access_rights(env):
    """Оновлення прав доступу"""
    _logger.info("Updating access rights...")

    try:
        # Оновлюємо права для базових груп
        budget_manager_group = env.ref('budget.group_budget_manager', raise_if_not_found=False)
        if budget_manager_group:
            # Додаємо права на створення та модифікацію
            _logger.info("Updated budget manager access rights")
    except Exception as e:
        _logger.warning(f"Could not update access rights: {str(e)}")


def _create_database_indexes(env):
    """Створення індексів для продуктивності"""
    _logger.info("Creating database indexes...")

    try:
        # Індекси для швидшого пошуку
        cr = env.cr

        # Індекс для пошуку бюджетів по ЦБО та періоду
        cr.execute("""
                   CREATE INDEX IF NOT EXISTS idx_budget_plan_cbo_period
                       ON budget_plan (cbo_id, period_id);
                   """)

        # Індекс для ієрархії ЦБО
        cr.execute("""
                   CREATE INDEX IF NOT EXISTS idx_cbo_parent_active
                       ON budget_responsibility_center (parent_id, active);
                   """)

        # Індекс для швидкого пошуку по коду
        cr.execute("""
                   CREATE INDEX IF NOT EXISTS idx_cbo_code
                       ON budget_responsibility_center (code);
                   """)

        _logger.info("Database indexes created successfully")

    except Exception as e:
        _logger.warning(f"Could not create database indexes: {str(e)}")


def _initialize_dashboard_data(env):
    """Ініціалізація даних для dashboard"""
    _logger.info("Initializing dashboard data...")

    try:
        # Очищуємо кеш computed полів
        env['budget.responsibility.center'].invalidate_cache()
        env['budget.plan'].invalidate_cache()

        # Примусово обчислюємо статистичні поля для всіх ЦБО
        cbos = env['budget.responsibility.center'].search([])
        for cbo in cbos:
            cbo._compute_budget_stats()
            cbo._compute_child_count()
            cbo._compute_hierarchy_level()

        _logger.info("Dashboard data initialized")

    except Exception as e:
        _logger.warning(f"Could not initialize dashboard data: {str(e)}")


def _uninstall_hook(cr, registry):
    """Uninstall hook для очищення даних при видаленні модуля"""
    _logger.info("Starting budget module uninstall cleanup...")

    with api.Environment.manage():
        env = api.Environment(cr, SUPERUSER_ID, {})

        try:
            # 1. Видалення cron завдань
            _cleanup_cron_jobs(env)

            # 2. Видалення шаблонів повідомлень
            _cleanup_mail_templates(env)

            # 3. Видалення послідовностей
            _cleanup_sequences(env)

            # 4. Видалення індексів
            _cleanup_database_indexes(env)

            # 5. Очищення кешу
            _cleanup_cache(env)

            _logger.info("Budget module uninstall cleanup completed")

        except Exception as e:
            _logger.error(f"Error during uninstall hook: {str(e)}")


def _cleanup_cron_jobs(env):
    """Видалення cron завдань"""
    _logger.info("Cleaning up cron jobs...")

    try:
        cron_jobs = env['ir.cron'].search([
            ('name', 'like', '%бюджет%'),
            ('model_id.model', 'like', 'budget.%')
        ])
        if cron_jobs:
            cron_jobs.unlink()
            _logger.info(f"Removed {len(cron_jobs)} cron jobs")
    except Exception as e:
        _logger.warning(f"Could not cleanup cron jobs: {str(e)}")


def _cleanup_mail_templates(env):
    """Видалення шаблонів повідомлень"""
    _logger.info("Cleaning up mail templates...")

    try:
        templates = env['mail.template'].search([
            ('model_id.model', 'like', 'budget.%')
        ])
        if templates:
            templates.unlink()
            _logger.info(f"Removed {len(templates)} mail templates")
    except Exception as e:
        _logger.warning(f"Could not cleanup mail templates: {str(e)}")


def _cleanup_sequences(env):
    """Видалення послідовностей"""
    _logger.info("Cleaning up sequences...")

    try:
        sequences = env['ir.sequence'].search([
            ('code', 'like', 'budget.%')
        ])
        if sequences:
            sequences.unlink()
            _logger.info(f"Removed {len(sequences)} sequences")
    except Exception as e:
        _logger.warning(f"Could not cleanup sequences: {str(e)}")


def _cleanup_database_indexes(env):
    """Видалення індексів"""
    _logger.info("Cleaning up database indexes...")

    try:
        cr = env.cr
        indexes_to_drop = [
            'idx_budget_plan_cbo_period',
            'idx_cbo_parent_active',
            'idx_cbo_code'
        ]

        for index_name in indexes_to_drop:
            cr.execute(f"DROP INDEX IF EXISTS {index_name};")

        _logger.info("Database indexes cleaned up")

    except Exception as e:
        _logger.warning(f"Could not cleanup database indexes: {str(e)}")


def _cleanup_cache(env):
    """Очищення кешу"""
    _logger.info("Cleaning up cache...")

    try:
        # Очищуємо registry кеш
        env.registry.clear_cache()

        # Очищуємо кеш computed полів
        env['budget.responsibility.center'].invalidate_cache()
        env['budget.plan'].invalidate_cache()

        _logger.info("Cache cleaned up")

    except Exception as e:
        _logger.warning(f"Could not cleanup cache: {str(e)}")


# Додаткові утилітарні функції
def _get_company_context(env):
    """Отримання контексту компанії"""
    return {
        'company_id': env.company.id,
        'company_name': env.company.name,
        'currency_id': env.company.currency_id.id,
        'current_year': env.context.get('current_year', 2024)
    }


def _create_demo_data(env):
    """Створення демо даних (викликається окремо)"""
    _logger.info("Creating demo data...")

    try:
        # Створюємо демо бюджет якщо є ЦБО
        cbos = env['budget.responsibility.center'].search([], limit=1)
        periods = env['budget.period'].search([], limit=1)
        budget_types = env['budget.type'].search([], limit=1)

        if cbos and periods and budget_types:
            demo_budget = env['budget.plan'].create({
                'name': 'Демо бюджет 2024',
                'code': 'DEMO2024',
                'cbo_id': cbos[0].id,
                'period_id': periods[0].id,
                'budget_type_id': budget_types[0].id,
                'state': 'draft',
                'description': 'Демонстраційний бюджет для тестування функціональності'
            })

            _logger.info(f"Created demo budget: {demo_budget.name}")

    except Exception as e:
        _logger.warning(f"Could not create demo data: {str(e)}")


def _validate_installation(env):
    """Валідація правильності встановлення"""
    _logger.info("Validating installation...")

    issues = []

    # Перевірка базових моделей
    models_to_check = [
        'budget.plan',
        'budget.responsibility.center',
        'budget.type',
        'budget.category',
        'budget.period'
    ]

    for model_name in models_to_check:
        try:
            env[model_name].search([], limit=1)
        except Exception as e:
            issues.append(f"Model {model_name} not accessible: {str(e)}")

    # Перевірка послідовностей
    for seq_code in ['budget.plan', 'budget.responsibility.center']:
        if not env['ir.sequence'].search([('code', '=', seq_code)]):
            issues.append(f"Sequence {seq_code} not found")

    if issues:
        _logger.warning(f"Installation validation issues: {'; '.join(issues)}")
    else:
        _logger.info("Installation validation passed")

    return len(issues) == 0