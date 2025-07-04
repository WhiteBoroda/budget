/** @odoo-module **/

import { Component, useState, onMounted } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

/**
 * Віджет ієрархічного дерева для ЦБО та бюджетів
 * Відображає структуру як у Windows Explorer
 */
export class HierarchyTreeWidget extends Component {
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");

        this.state = useState({
            treeData: [],
            expandedNodes: new Set(),
            selectedNode: null,
            loading: true,
        });

        onMounted(() => {
            this.loadTreeData();
        });
    }

    /**
     * Завантаження даних дерева з сервера
     */
    async loadTreeData() {
        try {
            this.state.loading = true;

            // Завантажуємо ЦБО з бюджетами
            const cboData = await this.orm.searchRead(
                "budget.responsibility.center",
                [["active", "=", true]],
                ["id", "name", "code", "cbo_type", "parent_id", "child_ids", "budget_count", "responsible_user_id"]
            );

            // Будуємо дерево
            this.state.treeData = this.buildTree(cboData);
            this.state.loading = false;

        } catch (error) {
            console.error("Помилка завантаження дерева:", error);
            this.state.loading = false;
        }
    }

    /**
     * Побудова ієрархічного дерева з плоского списку
     */
    buildTree(flatData) {
        const itemsMap = new Map();
        const tree = [];

        // Створюємо мапу всіх елементів
        flatData.forEach(item => {
            itemsMap.set(item.id, {
                ...item,
                children: [],
                icon: this.getNodeIcon(item.cbo_type),
                expanded: false,
                hasChildren: item.child_ids && item.child_ids.length > 0
            });
        });

        // Будуємо ієрархію
        flatData.forEach(item => {
            const node = itemsMap.get(item.id);

            if (item.parent_id && item.parent_id[0]) {
                const parent = itemsMap.get(item.parent_id[0]);
                if (parent) {
                    parent.children.push(node);
                }
            } else {
                tree.push(node);
            }
        });

        return tree;
    }

    /**
     * Отримання іконки для типу ЦБО
     */
    getNodeIcon(cboType) {
        const icons = {
            'holding': '🏛️',
            'enterprise': '🏭',
            'business_direction': '🏢',
            'department': '🏪',
            'division': '📁',
            'office': '🏬',
            'team': '👥',
            'project': '📊'
        };
        return icons[cboType] || '📂';
    }

    /**
     * Розгортання/згортання вузла
     */
    toggleNode(nodeId) {
        if (this.state.expandedNodes.has(nodeId)) {
            this.state.expandedNodes.delete(nodeId);
        } else {
            this.state.expandedNodes.add(nodeId);
        }
    }

    /**
     * Вибір вузла
     */
    selectNode(node) {
        this.state.selectedNode = node.id;

        // Викликаємо подію вибору
        this.props.onNodeSelect && this.props.onNodeSelect(node);
    }

    /**
     * Подвійний клік - відкриття форми ЦБО
     */
    async openNode(node) {
        await this.action.doAction({
            type: 'ir.actions.act_window',
            name: `ЦБО: ${node.name}`,
            res_model: 'budget.responsibility.center',
            res_id: node.id,
            view_mode: 'form',
            target: 'current'
        });
    }

    /**
     * Перегляд бюджетів ЦБО
     */
    async viewBudgets(node) {
        await this.action.doAction({
            type: 'ir.actions.act_window',
            name: `Бюджети: ${node.name}`,
            res_model: 'budget.plan',
            view_mode: 'tree,form',
            domain: [['cbo_id', '=', node.id]],
            context: { default_cbo_id: node.id }
        });
    }

    /**
     * Створення нового бюджету
     */
    async createBudget(node) {
        await this.action.doAction({
            type: 'ir.actions.act_window',
            name: `Новий бюджет для ${node.name}`,
            res_model: 'budget.plan',
            view_mode: 'form',
            target: 'new',
            context: {
                default_cbo_id: node.id,
                default_state: 'draft'
            }
        });
    }

    /**
     * Рендеринг вузла дерева
     */
    renderNode(node, level = 0) {
        const isExpanded = this.state.expandedNodes.has(node.id);
        const isSelected = this.state.selectedNode === node.id;
        const hasChildren = node.children && node.children.length > 0;

        return `
            <div class="tree-node" data-level="${level}">
                <!-- Лінія відступу -->
                <div class="tree-indent" style="width: ${level * 20}px;"></div>
                
                <!-- Кнопка розгортання -->
                <div class="tree-toggle ${hasChildren ? 'has-children' : ''}" 
                     onclick="this.closest('.hierarchy-tree-widget').component.toggleNode(${node.id})">
                    ${hasChildren ? (isExpanded ? '▼' : '▶') : ''}
                </div>
                
                <!-- Іконка та назва -->
                <div class="tree-content ${isSelected ? 'selected' : ''}"
                     onclick="this.closest('.hierarchy-tree-widget').component.selectNode(${JSON.stringify(node)})"
                     ondblclick="this.closest('.hierarchy-tree-widget').component.openNode(${JSON.stringify(node)})">
                    
                    <span class="tree-icon">${node.icon}</span>
                    <span class="tree-label">${node.name}</span>
                    <span class="tree-code">(${node.code})</span>
                    
                    <!-- Індикатор бюджетів -->
                    ${node.budget_count > 0 ? `<span class="budget-indicator">${node.budget_count} 📊</span>` : ''}
                </div>
                
                <!-- Дії -->
                <div class="tree-actions">
                    ${node.budget_count > 0 ? 
                        `<button class="btn-sm btn-outline-primary" 
                                onclick="this.closest('.hierarchy-tree-widget').component.viewBudgets(${JSON.stringify(node)})"
                                title="Переглянути бюджети">📊</button>` : ''}
                    
                    <button class="btn-sm btn-outline-success" 
                            onclick="this.closest('.hierarchy-tree-widget').component.createBudget(${JSON.stringify(node)})"
                            title="Створити бюджет">➕</button>
                </div>
            </div>
            
            <!-- Дочірні вузли -->
            ${isExpanded && hasChildren ? 
                node.children.map(child => this.renderNode(child, level + 1)).join('') : ''}
        `;
    }

    /**
     * Основний рендеринг компонента
     */
    render() {
        if (this.state.loading) {
            return `
                <div class="hierarchy-tree-widget loading">
                    <div class="loading-spinner">
                        <i class="fa fa-spinner fa-spin"></i> Завантаження структури...
                    </div>
                </div>
            `;
        }

        return `
            <div class="hierarchy-tree-widget" data-component="this">
                <div class="tree-header">
                    <h4>Структура організації</h4>
                    <div class="tree-controls">
                        <button class="btn btn-sm btn-outline-secondary" 
                                onclick="this.closest('.hierarchy-tree-widget').component.expandAll()">
                            Розгорнути все
                        </button>
                        <button class="btn btn-sm btn-outline-secondary"
                                onclick="this.closest('.hierarchy-tree-widget').component.collapseAll()">
                            Згорнути все
                        </button>
                        <button class="btn btn-sm btn-outline-primary"
                                onclick="this.closest('.hierarchy-tree-widget').component.loadTreeData()">
                            🔄 Оновити
                        </button>
                    </div>
                </div>
                
                <div class="tree-container">
                    ${this.state.treeData.map(node => this.renderNode(node)).join('')}
                </div>
                
                ${this.state.treeData.length === 0 ? 
                    `<div class="tree-empty">
                        <p>📂 Структура організації порожня</p>
                        <p>Додайте ЦБО для відображення дерева</p>
                    </div>` : ''}
            </div>
        `;
    }

    /**
     * Розгортання всіх вузлів
     */
    expandAll() {
        const expandNodes = (nodes) => {
            nodes.forEach(node => {
                if (node.hasChildren) {
                    this.state.expandedNodes.add(node.id);
                    if (node.children) {
                        expandNodes(node.children);
                    }
                }
            });
        };

        expandNodes(this.state.treeData);
    }

    /**
     * Згортання всіх вузлів
     */
    collapseAll() {
        this.state.expandedNodes.clear();
    }
}

HierarchyTreeWidget.template = "budget.HierarchyTreeWidget";

// Реєстрація віджета
registry.category("fields").add("hierarchy_tree", HierarchyTreeWidget);

/**
 * Бюджетне дерево з консолідацією
 */
export class BudgetTreeWidget extends HierarchyTreeWidget {

    async loadTreeData() {
        try {
            this.state.loading = true;

            // Завантажуємо бюджети з ЦБО
            const budgetData = await this.orm.searchRead(
                "budget.plan",
                [],
                ["id", "name", "cbo_id", "period_id", "budget_type_id", "state",
                 "total_planned_amount", "consolidation_level", "is_consolidated",
                 "parent_budget_id", "child_budget_ids"]
            );

            this.state.treeData = this.buildBudgetTree(budgetData);
            this.state.loading = false;

        } catch (error) {
            console.error("Помилка завантаження бюджетного дерева:", error);
            this.state.loading = false;
        }
    }

    buildBudgetTree(budgetData) {
        // Групуємо по consolidation_level і cbo_id
        const tree = [];
        const itemsMap = new Map();

        budgetData.forEach(budget => {
            itemsMap.set(budget.id, {
                ...budget,
                children: [],
                icon: this.getBudgetIcon(budget.consolidation_level, budget.is_consolidated),
                expanded: false,
                hasChildren: budget.child_budget_ids && budget.child_budget_ids.length > 0
            });
        });

        // Будуємо ієрархію бюджетів
        budgetData.forEach(budget => {
            const node = itemsMap.get(budget.id);

            if (budget.parent_budget_id && budget.parent_budget_id[0]) {
                const parent = itemsMap.get(budget.parent_budget_id[0]);
                if (parent) {
                    parent.children.push(node);
                }
            } else {
                tree.push(node);
            }
        });

        return tree;
    }

    getBudgetIcon(consolidationLevel, isConsolidated) {
        if (isConsolidated) {
            return consolidationLevel === 'holding' ? '🏛️' :
                   consolidationLevel === 'company' ? '🏭' : '📊';
        }
        return '💰';
    }
}

registry.category("fields").add("budget_tree", BudgetTreeWidget);