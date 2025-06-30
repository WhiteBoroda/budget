/** @odoo-module **/
// static/src/js/budget_widgets.js
// JavaScript виджеты для системы бюджетирования в Odoo 17

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

// Виджет панели управления бюджетами
export class BudgetDashboardWidget extends Component {
    static template = "budget.BudgetDashboardWidget";

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
            const data = await this.rpc("/budget/dashboard/data", {
                period_id: this.props.period_id || false
            });

            Object.assign(this.state, data);
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

    onViewOverdue() {
        this.env.services.action.doAction({
            type: 'ir.actions.act_window',
            name: 'Прострочені бюджети',
            res_model: 'budget.plan',
            view_mode: 'tree,form',
            domain: [
                ['submission_deadline', '<', new Date().toISOString().split('T')[0]],
                ['state', '!=', 'approved']
            ],
            target: 'current'
        });
    }
}

// Виджет прогресса выполнения бюджета
export class BudgetProgressWidget extends Component {
    static template = "budget.BudgetProgressWidget";
    static props = {
        planned: { type: Number },
        actual: { type: Number },
        variance: { type: Number, optional: true }
    };

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

    get varianceClass() {
        if (!this.props.variance) return "";
        return this.props.variance < 0 ? "text-danger" : "text-success";
    }
}

// Виджет быстрого создания прогноза
export class QuickForecastWidget extends Component {
    static template = "budget.QuickForecastWidget";

    setup() {
        this.rpc = useService("rpc");
        this.notification = useService("notification");

        this.state = useState({
            teams: [],
            selectedTeam: null,
            periods: [],
            selectedPeriod: null,
            loading: false
        });

        onWillStart(async () => {
            await this.loadData();
        });
    }

    async loadData() {
        try {
            const [teams, periods] = await Promise.all([
                this.rpc("/web/dataset/search_read", {
                    model: "crm.team",
                    fields: ["id", "name"],
                    domain: []
                }),
                this.rpc("/web/dataset/search_read", {
                    model: "budget.period",
                    fields: ["id", "name"],
                    domain: [["state", "=", "planning"]]
                })
            ]);

            this.state.teams = teams.records;
            this.state.periods = periods.records;
        } catch (error) {
            this.notification.add("Помилка завантаження даних", {
                type: "danger"
            });
        }
    }

    async onCreateForecast() {
        if (!this.state.selectedTeam || !this.state.selectedPeriod) {
            this.notification.add("Оберіть команду та період", {
                type: "warning"
            });
            return;
        }

        this.state.loading = true;

        try {
            const result = await this.rpc("/budget/forecast/quick_create", {
                team_id: this.state.selectedTeam,
                period_id: this.state.selectedPeriod
            });

            if (result.success) {
                this.notification.add("Прогноз створено успішно!", {
                    type: "success"
                });

                // Переход к созданному прогнозу
                this.env.services.action.doAction({
                    type: 'ir.actions.act_window',
                    res_model: 'sale.forecast',
                    res_id: result.forecast_id,
                    view_mode: 'form',
                    target: 'current'
                });
            }
        } catch (error) {
            this.notification.add("Помилка створення прогнозу", {
                type: "danger"
            });
        } finally {
            this.state.loading = false;
        }
    }
}

// Виджет аналитики бюджетов
export class BudgetAnalyticsWidget extends Component {
    static template = "budget.BudgetAnalyticsWidget";

    setup() {
        this.rpc = useService("rpc");
        this.state = useState({
            chartData: null,
            loading: true
        });

        onWillStart(async () => {
            await this.loadChartData();
        });
    }

    async loadChartData() {
        try {
            const data = await this.rpc("/budget/analytics/chart_data", {
                period_id: this.props.period_id || false,
                chart_type: this.props.chart_type || 'execution'
            });

            this.state.chartData = data;
            this.state.loading = false;

            // Инициализация Chart.js после загрузки данных
            this.renderChart();
        } catch (error) {
            console.error("Ошибка загрузки данных аналитики:", error);
            this.state.loading = false;
        }
    }

    renderChart() {
        // Здесь будет код для рендеринга графика с Chart.js
        if (this.state.chartData && typeof Chart !== 'undefined') {
            const ctx = this.el.querySelector('#budgetChart');
            new Chart(ctx, {
                type: 'bar',
                data: this.state.chartData,
                options: {
                    responsive: true,
                    plugins: {
                        title: {
                            display: true,
                            text: 'Виконання бюджетів'
                        }
                    }
                }
            });
        }
    }
}

// Регистрация виджетов в реестре Odoo 17
registry.category("fields").add("budget_dashboard", BudgetDashboardWidget);
registry.category("fields").add("budget_progress", BudgetProgressWidget);
registry.category("fields").add("quick_forecast", QuickForecastWidget);
registry.category("fields").add("budget_analytics", BudgetAnalyticsWidget);

// Дополнительные утилиты для работы с бюджетами
export const BudgetUtils = {
    formatCurrency(amount, currency = "UAH") {
        return new Intl.NumberFormat('uk-UA', {
            style: 'currency',
            currency: currency,
            minimumFractionDigits: 2
        }).format(amount);
    },

    formatPercent(value) {
        return new Intl.NumberFormat('uk-UA', {
            style: 'percent',
            minimumFractionDigits: 1
        }).format(value / 100);
    },

    getVarianceColor(variance) {
        if (variance < -10) return 'danger';
        if (variance < -5) return 'warning';
        if (variance > 5) return 'info';
        return 'success';
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

// Экспорт утилит
window.BudgetUtils = BudgetUtils;