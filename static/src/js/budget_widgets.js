/** @odoo-module **/
// static/src/js/budget_widgets.js
// JavaScript виджети для системи бюджетування в Odoo 17

import { Component, useState, onWillStart, xml } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

// Виджет панелі управління бюджетами
export class BudgetDashboardWidget extends Component {
    static template = xml`
        <div class="budget-dashboard-widget">
            <div t-if="state.loading" class="text-center">
                <i class="fa fa-spinner fa-spin"/>
                <span> Завантаження...</span>
            </div>
            
            <div t-else="" class="budget-dashboard-content">
                <div class="row">
                    <div class="col-md-3">
                        <div class="card text-center">
                            <div class="card-body">
                                <h5 class="card-title">📋 Всього бюджетів</h5>
                                <h2 class="text-primary" t-esc="state.totalBudgets"/>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <div class="card text-center">
                            <div class="card-body">
                                <h5 class="card-title">✅ Затверджені</h5>
                                <h2 class="text-success" t-esc="state.approvedBudgets"/>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <div class="card text-center">
                            <div class="card-body">
                                <h5 class="card-title">⏳ Очікують</h5>
                                <h2 class="text-warning" t-esc="state.pendingBudgets"/>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <div class="card text-center">
                            <div class="card-body">
                                <h5 class="card-title">⚠️ Прострочені</h5>
                                <h2 class="text-danger" t-esc="state.overdueBudgets"/>
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="mt-3 text-center">
                    <button class="btn btn-primary me-2" t-on-click="onViewBudgets">
                        📋 Переглянути всі бюджети
                    </button>
                    <button class="btn btn-secondary" t-on-click="onRefreshClick">
                        🔄 Оновити
                    </button>
                </div>
            </div>
        </div>
    `;

    setup() {
        this.rpc = useService("rpc");
        this.notification = useService("notification");

        this.state = useState({
            totalBudgets: 0,
            approvedBudgets: 0,
            pendingBudgets: 0,
            overdueBudgets: 0,
            totalPlanned: 0,
            totalActual: 0,
            loading: true
        });

        onWillStart(async () => {
            await this.loadDashboardData();
        });
    }

    async loadDashboardData() {
        try {
            // Простий підхід без RPC поки що
            this.state.totalBudgets = 10;
            this.state.approvedBudgets = 5;
            this.state.pendingBudgets = 3;
            this.state.overdueBudgets = 2;
            this.state.totalPlanned = 100000;
            this.state.totalActual = 85000;
            this.state.loading = false;
        } catch (error) {
            this.notification.add("Помилка завантаження даних панелі", {
                type: "danger"
            });
            this.state.loading = false;
        }
    }

    async onRefreshClick() {
        this.state.loading = true;
        await this.loadDashboardData();
    }

    onViewBudgets() {
        this.env.services.action.doAction({
            type: 'ir.actions.act_window',
            name: 'Всі бюджети',
            res_model: 'budget.plan',
            view_mode: 'kanban,tree,form',
            target: 'current'
        });
    }
}

// Виджет БДР Dashboard
export class BdrDashboardWidget extends Component {
    static template = xml`
        <div class="bdr-dashboard-widget">
            <div t-if="state.loading" class="text-center">
                <i class="fa fa-spinner fa-spin"/>
                <span> Завантаження даних БДР...</span>
            </div>
            
            <div t-else="" class="bdr-dashboard-content">
                <h3 class="text-center mb-4">💼 Бюджет доходів і витрат (БДР)</h3>
                
                <div class="row">
                    <div class="col-md-4">
                        <div class="card text-center border-success">
                            <div class="card-body">
                                <h5 class="card-title">💰 Загальні доходи</h5>
                                <h2 class="text-success" t-esc="state.totalIncome"/>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-4">
                        <div class="card text-center border-danger">
                            <div class="card-body">
                                <h5 class="card-title">💸 Загальні витрати</h5>
                                <h2 class="text-danger" t-esc="state.totalExpenses"/>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-4">
                        <div class="card text-center border-info">
                            <div class="card-body">
                                <h5 class="card-title">📈 Чистий прибуток</h5>
                                <h2 class="text-info" t-esc="state.netProfit"/>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="mt-3 text-center">
                    <button class="btn btn-primary me-2" t-on-click="onViewBdrWizard">
                        🧙‍♂️ Майстер БДР
                    </button>
                    <button class="btn btn-secondary" t-on-click="onRefreshClick">
                        🔄 Оновити
                    </button>
                </div>
            </div>
        </div>
    `;

    setup() {
        this.rpc = useService("rpc");
        this.notification = useService("notification");

        this.state = useState({
            totalIncome: 0,
            totalExpenses: 0,
            netProfit: 0,
            loading: true
        });

        onWillStart(async () => {
            await this.loadBdrData();
        });
    }

    async loadBdrData() {
        try {
            // Простий підхід без RPC поки що
            this.state.totalIncome = 500000;
            this.state.totalExpenses = 350000;
            this.state.netProfit = 150000;
            this.state.loading = false;
        } catch (error) {
            this.notification.add("Помилка завантаження даних БДР", {
                type: "danger"
            });
            this.state.loading = false;
        }
    }

    async onRefreshClick() {
        this.state.loading = true;
        await this.loadBdrData();
    }

    onViewBdrWizard() {
        this.env.services.action.doAction({
            type: 'ir.actions.act_window',
            name: 'Робота з БДР',
            res_model: 'bdr.budget.wizard',
            view_mode: 'form',
            target: 'new'
        });
    }
}

// Виджет прогресу
export class BudgetProgressWidget extends Component {
    static template = xml`
        <div class="budget-progress-widget">
            <div class="progress-info d-flex justify-content-between mb-2">
                <span>Планово: <t t-esc="props.planned or 0"/></span>
                <span>Фактично: <t t-esc="props.actual or 0"/></span>
                <span><t t-esc="executionPercent"/>%</span>
            </div>
            <div class="progress">
                <div class="progress-bar" 
                     t-att-class="progressBarClass"
                     t-att-style="'width: ' + executionPercent + '%'">
                </div>
            </div>
        </div>
    `;

    setup() {
        // Простий виджет без складної логіки
    }

    get executionPercent() {
        if (!this.props.planned) return 0;
        return Math.round((this.props.actual / this.props.planned) * 100);
    }

    get progressBarClass() {
        const percent = this.executionPercent;
        if (percent < 50) return "bg-danger";
        if (percent < 80) return "bg-warning";
        if (percent > 100) return "bg-info";
        return "bg-success";
    }
}

// Виджет швидкого прогнозу
export class QuickForecastWidget extends Component {
    static template = xml`
        <div class="quick-forecast-widget">
            <h5>🚀 Швидке створення прогнозу</h5>
            <div class="text-center">
                <button class="btn btn-success" t-on-click="onCreateForecast">
                    ➕ Створити прогноз
                </button>
            </div>
        </div>
    `;

    setup() {
        this.notification = useService("notification");
    }

    async onCreateForecast() {
        this.notification.add("Функція в розробці", {
            type: "info"
        });
    }
}

// Виджет аналітики
export class BudgetAnalyticsWidget extends Component {
    static template = xml`
        <div class="budget-analytics-widget">
            <h5>📊 Аналітика бюджетів</h5>
            <div class="text-center text-muted">
                <p>Графік буде доступний незабаром</p>
            </div>
        </div>
    `;

    setup() {
        // Простий виджет
    }
}

// Реєстрація виджетів
registry.category("fields").add("budget_dashboard", BudgetDashboardWidget);
registry.category("fields").add("bdr_dashboard", BdrDashboardWidget);
registry.category("fields").add("budget_progress", BudgetProgressWidget);
registry.category("fields").add("quick_forecast", QuickForecastWidget);
registry.category("fields").add("budget_analytics", BudgetAnalyticsWidget);

// Утиліти
export const BudgetUtils = {
    formatCurrency(amount, currency = "UAH") {
        return new Intl.NumberFormat('uk-UA', {
            style: 'currency',
            currency: currency,
            minimumFractionDigits: 2
        }).format(amount);
    },

    getStatusBadge(state) {
        const badges = {
            'draft': { class: 'secondary', text: 'Чернетка' },
            'planning': { class: 'primary', text: 'Планування' },
            'coordination': { class: 'warning', text: 'Узгодження' },
            'approved': { class: 'success', text: 'Затверджений' },
            'executed': { class: 'info', text: 'Виконується' },
            'closed': { class: 'dark', text: 'Закритий' }
        };
        return badges[state] || { class: 'secondary', text: state };
    }
};

// Експорт утилітів
window.BudgetUtils = BudgetUtils;