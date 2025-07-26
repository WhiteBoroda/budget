/** @odoo-module **/
// Віджети для системи бюджетування - ПОВНІСТЮ СУМІСНІ З ODOO 17

import { Component, useState, onWillStart, xml } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { formatCurrency } from "@web/core/utils/numbers";

/**
 * Віджет панелі управління бюджетами
 */
export class BudgetDashboardWidget extends Component {
    static template = xml`
        <div class="budget-dashboard-widget">
            <div t-if="state.loading" class="text-center p-4">
                <i class="fa fa-spinner fa-spin fa-2x text-primary"/>
                <div class="mt-2">Завантаження статистики бюджетів...</div>
            </div>
            
            <div t-else="" class="budget-dashboard-content">
                <div class="row g-3">
                    <!-- Загальна статистика -->
                    <div class="col-md-3">
                        <div class="card border-primary">
                            <div class="card-body text-center">
                                <i class="fa fa-chart-line fa-2x text-primary mb-2"/>
                                <h5 class="card-title">Всього бюджетів</h5>
                                <h2 class="text-primary mb-0" t-esc="state.totalBudgets"/>
                                <small class="text-muted">активних плани</small>
                            </div>
                        </div>
                    </div>
                    
                    <div class="col-md-3">
                        <div class="card border-success">
                            <div class="card-body text-center">
                                <i class="fa fa-check-circle fa-2x text-success mb-2"/>
                                <h5 class="card-title">Затверджені</h5>
                                <h2 class="text-success mb-0" t-esc="state.approvedBudgets"/>
                                <small class="text-muted">готові до виконання</small>
                            </div>
                        </div>
                    </div>
                    
                    <div class="col-md-3">
                        <div class="card border-warning">
                            <div class="card-body text-center">
                                <i class="fa fa-clock-o fa-2x text-warning mb-2"/>
                                <h5 class="card-title">Очікують</h5>
                                <h2 class="text-warning mb-0" t-esc="state.pendingBudgets"/>
                                <small class="text-muted">на затвердженні</small>
                            </div>
                        </div>
                    </div>
                    
                    <div class="col-md-3">
                        <div class="card border-danger">
                            <div class="card-body text-center">
                                <i class="fa fa-exclamation-triangle fa-2x text-danger mb-2"/>
                                <h5 class="card-title">Прострочені</h5>
                                <h2 class="text-danger mb-0" t-esc="state.overdueBudgets"/>
                                <small class="text-muted">потребують уваги</small>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Фінансові показники -->
                <div class="row g-3 mt-3">
                    <div class="col-md-4">
                        <div class="card">
                            <div class="card-header bg-light">
                                <h6 class="mb-0">💰 Планова сума</h6>
                            </div>
                            <div class="card-body text-center">
                                <h3 class="text-primary" t-esc="state.formattedPlannedAmount"/>
                                <div class="progress mt-2">
                                    <div class="progress-bar bg-primary"
                                         t-att-style="'width: ' + state.plannedPercentage + '%'"/>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <div class="col-md-4">
                        <div class="card">
                            <div class="card-header bg-light">
                                <h6 class="mb-0">✅ Фактично виконано</h6>
                            </div>
                            <div class="card-body text-center">
                                <h3 class="text-success" t-esc="state.formattedActualAmount"/>
                                <div class="progress mt-2">
                                    <div class="progress-bar bg-success"
                                         t-att-style="'width: ' + state.executionPercentage + '%'"/>
                                </div>
                                <small class="text-muted" t-esc="state.executionPercentage + '% виконання'"/>
                            </div>
                        </div>
                    </div>
                    
                    <div class="col-md-4">
                        <div class="card">
                            <div class="card-header bg-light">
                                <h6 class="mb-0">💳 Доступно</h6>
                            </div>
                            <div class="card-body text-center">
                                <h3 class="text-info" t-esc="state.formattedAvailableAmount"/>
                                <div class="progress mt-2">
                                    <div class="progress-bar bg-info"
                                         t-att-style="'width: ' + state.availablePercentage + '%'"/>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Швидкі дії -->
                <div class="row g-3 mt-3">
                    <div class="col-12">
                        <div class="card">
                            <div class="card-header">
                                <h6 class="mb-0">🚀 Швидкі дії</h6>
                            </div>
                            <div class="card-body">
                                <div class="d-flex flex-wrap gap-2">
                                    <button class="btn btn-primary" t-on-click="createBudget">
                                        <i class="fa fa-plus"/> Створити бюджет
                                    </button>
                                    <button class="btn btn-outline-secondary" t-on-click="viewAllBudgets">
                                        <i class="fa fa-list"/> Всі бюджети
                                    </button>
                                    <button class="btn btn-outline-info" t-on-click="viewReports">
                                        <i class="fa fa-chart-bar"/> Звіти
                                    </button>
                                    <button class="btn btn-outline-success" t-on-click="refreshData">
                                        <i class="fa fa-refresh"/> Оновити
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `;

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");

        this.state = useState({
            loading: true,
            totalBudgets: 0,
            approvedBudgets: 0,
            pendingBudgets: 0,
            overdueBudgets: 0,
            plannedAmount: 0,
            actualAmount: 0,
            availableAmount: 0,
            formattedPlannedAmount: "0",
            formattedActualAmount: "0",
            formattedAvailableAmount: "0",
            plannedPercentage: 0,
            executionPercentage: 0,
            availablePercentage: 0
        });

        onWillStart(async () => {
            await this.loadDashboardData();
        });
    }

    /**
     * Завантаження даних для dashboard
     */
    async loadDashboardData() {
        try {
            this.state.loading = true;

            const data = await this.orm.call(
                "budget.plan",
                "get_dashboard_data",
                []
            );

            // Оновлюємо стан з отриманими даними
            Object.assign(this.state, {
                totalBudgets: data.total_budgets || 0,
                approvedBudgets: data.approved_budgets || 0,
                pendingBudgets: data.pending_budgets || 0,
                overdueBudgets: data.overdue_budgets || 0,
                plannedAmount: data.planned_amount || 0,
                actualAmount: data.actual_amount || 0,
                availableAmount: data.available_amount || 0
            });

            // Форматуємо суми
            this.formatAmounts();
            this.calculatePercentages();

        } catch (error) {
            this.notification.add(
                "Помилка завантаження dashboard",
                { type: "danger" }
            );
            console.error("Dashboard loading error:", error);
        } finally {
            this.state.loading = false;
        }
    }

    /**
     * Форматування сум
     */
    formatAmounts() {
        this.state.formattedPlannedAmount = formatCurrency(this.state.plannedAmount);
        this.state.formattedActualAmount = formatCurrency(this.state.actualAmount);
        this.state.formattedAvailableAmount = formatCurrency(this.state.availableAmount);
    }

    /**
     * Розрахунок відсотків
     */
    calculatePercentages() {
        const total = this.state.plannedAmount;
        if (total > 0) {
            this.state.executionPercentage = Math.round((this.state.actualAmount / total) * 100);
            this.state.availablePercentage = Math.round((this.state.availableAmount / total) * 100);
            this.state.plannedPercentage = 100;
        } else {
            this.state.executionPercentage = 0;
            this.state.availablePercentage = 0;
            this.state.plannedPercentage = 0;
        }
    }

    /**
     * Створення нового бюджету
     */
    async createBudget() {
        return this.action.doAction({
            name: "Новий бюджет",
            type: "ir.actions.act_window",
            res_model: "budget.plan",
            view_mode: "form",
            views: [[false, "form"]],
            target: "new"
        });
    }

    /**
     * Перегляд всіх бюджетів
     */
    async viewAllBudgets() {
        return this.action.doAction({
            name: "Всі бюджети",
            type: "ir.actions.act_window",
            res_model: "budget.plan",
            view_mode: "tree,form",
            views: [[false, "tree"], [false, "form"]]
        });
    }

    /**
     * Перегляд звітів
     */
    async viewReports() {
        return this.action.doAction({
            name: "Звіти по бюджетах",
            type: "ir.actions.act_window",
            res_model: "budget.report",
            view_mode: "tree,form",
            views: [[false, "tree"], [false, "form"]]
        });
    }

    /**
     * Оновлення даних
     */
    async refreshData() {
        await this.loadDashboardData();
        this.notification.add(
            "Дані оновлено",
            { type: "success" }
        );
    }
}

/**
 * Віджет статистики ЦБО
 */
export class CboStatsWidget extends Component {
    static template = xml`
        <div class="cbo-stats-widget">
            <div t-if="state.loading" class="text-center p-3">
                <i class="fa fa-spinner fa-spin"/>
                <span class="ms-2">Завантаження статистики ЦБО...</span>
            </div>
            
            <div t-else="" class="cbo-stats-content">
                <div class="row g-2">
                    <div class="col-md-6">
                        <div class="stat-card">
                            <div class="stat-icon">🏢</div>
                            <div class="stat-content">
                                <div class="stat-value" t-esc="state.totalCbos"/>
                                <div class="stat-label">Всього ЦБО</div>
                            </div>
                        </div>
                    </div>
                    
                    <div class="col-md-6">
                        <div class="stat-card">
                            <div class="stat-icon">📊</div>
                            <div class="stat-content">
                                <div class="stat-value" t-esc="state.activeBudgets"/>
                                <div class="stat-label">Активних бюджетів</div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `;

    setup() {
        this.orm = useService("orm");

        this.state = useState({
            loading: true,
            totalCbos: 0,
            activeBudgets: 0
        });

        onWillStart(async () => {
            await this.loadStats();
        });
    }

    async loadStats() {
        try {
            const data = await this.orm.call(
                "budget.responsibility.center",
                "get_stats_summary",
                []
            );

            this.state.totalCbos = data.total_cbos || 0;
            this.state.activeBudgets = data.active_budgets || 0;
        } catch (error) {
            console.error("CBO stats loading error:", error);
        } finally {
            this.state.loading = false;
        }
    }
}

// Реєстрація віджетів
registry.category("fields").add("budget_dashboard_widget", BudgetDashboardWidget);
registry.category("fields").add("cbo_stats_widget", CboStatsWidget);