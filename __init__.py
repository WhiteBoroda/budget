# -*- coding: utf-8 -*-
"""
Система бюджетного планування та контролю
==========================================

Модуль для комплексного управління бюджетним процесом з підтримкою:
- Ієрархічної структури ЦБО
- Інтеграції з прогнозами продажів
- Багаторівневого планування та контролю
- Аналітики та звітності

Сумісність: Odoo 17.0+
Автор: HD Digital Solution
"""

from . import models
from . import wizard
from . import report
from .hooks import _post_init_hook, _uninstall_hook

# Імпорт всіх моделей
from .models import (
    budget_config,
    budget_plan,
    budget_execution,
    budget_category,
    budget_cbo_extention,
    sales_forecast,
    project_views
)

# Імпорт всіх wizard'ів
from .wizard import (
    budget_wizard,
    sales_forecast_wizard,
    budget_import_wizard,
    budget_approval_wizard
)

# Експорт hooks для маніфесту
__all__ = [
    '_post_init_hook',
    '_uninstall_hook'
]