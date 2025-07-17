/** @odoo-module **/

import { Component, useState, onWillStart, onMounted, useRef } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

/**
 * Віджет ієрархічного дерева для ЦБО - СУМІСНИЙ З ODOO 17
 */
export class HierarchyTreeWidget extends Component {
    static template = "budget.HierarchyTreeWidget";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");

        this.treeRef = useRef("tree-container");

        this.state = useState({
            treeData: [],
            loading: true,
            selectedNode: null,
            expandedNodes: new Set(),
            searchQuery: ''
        });

        onWillStart(async () => {
            await this.loadTreeData();
        });

        onMounted(() => {
            this.setupEventListeners();
        });
    }

    /**
     * Завантаження даних дерева
     */
    async loadTreeData() {
        try {
            this.state.loading = true;
            const data = await this.orm.call(
                "budget.responsibility.center",
                "get_hierarchy_tree",
                []
            );
            this.state.treeData = data;
        } catch (error) {
            this.notification.add("Помилка завантаження дерева", { type: "danger" });
            console.error("Tree loading error:", error);
        } finally {
            this.state.loading = false;
        }
    }

    /**
     * Налаштування обробників подій
     */
    setupEventListeners() {
        document.addEventListener('click', this.handleDocumentClick.bind(this));
    }

    /**
     * Обробка кліків по документу
     */
    handleDocumentClick(event) {
        // Скидання виділення при кліку поза деревом
        if (!event.target.closest('.hierarchy-tree-widget')) {
            this.state.selectedNode = null;
        }
    }

    /**
     * Перемикання розгортання/згортання вузла
     */
    async toggleNode(nodeId) {
        if (this.state.expandedNodes.has(nodeId)) {
            this.state.expandedNodes.delete(nodeId);
        } else {
            this.state.expandedNodes.add(nodeId);
        }
    }

    /**
     * Виділення вузла
     */
    selectNode(nodeId) {
        this.state.selectedNode = nodeId;
    }

    /**
     * Розгортання всіх вузлів
     */
    expandAll() {
        const addAllNodes = (nodes) => {
            nodes.forEach(node => {
                if (node.children && node.children.length > 0) {
                    this.state.expandedNodes.add(node.id);
                    addAllNodes(node.children);
                }
            });
        };
        addAllNodes(this.state.treeData);
    }

    /**
     * Згортання всіх вузлів
     */
    collapseAll() {
        this.state.expandedNodes.clear();
    }

    /**
     * Перегляд бюджетів вузла
     */
    async viewBudgets(node) {
        try {
            const action = await this.orm.call(
                "budget.responsibility.center",
                "action_view_budgets",
                [node.id]
            );
            this.action.doAction(action);
        } catch (error) {
            this.notification.add("Помилка відкриття бюджетів", { type: "danger" });
        }
    }

    /**
     * Створення нового бюджету
     */
    async createBudget(node) {
        try {
            const action = await this.orm.call(
                "budget.responsibility.center",
                "action_create_budget",
                [node.id]
            );
            this.action.doAction(action);
        } catch (error) {
            this.notification.add("Помилка створення бюджету", { type: "danger" });
        }
    }

    /**
     * Відкриття форми ЦБО
     */
    async openNodeForm(node) {
        const action = {
            type: 'ir.actions.act_window',
            res_model: 'budget.responsibility.center',
            res_id: node.id,
            view_mode: 'form',
            target: 'new'
        };
        this.action.doAction(action);
    }

    /**
     * Створення дочірнього ЦБО
     */
    async createChildNode(parentNode) {
        const action = {
            type: 'ir.actions.act_window',
            res_model: 'budget.responsibility.center',
            view_mode: 'form',
            context: {
                default_parent_id: parentNode.id,
                default_cbo_type: this._getDefaultChildType(parentNode.cbo_type),
                default_budget_level: this._getDefaultChildLevel(parentNode.budget_level)
            },
            target: 'new'
        };
        this.action.doAction(action);
    }

    /**
     * Пошук в дереві
     */
    onSearchInput(event) {
        this.state.searchQuery = event.target.value;
        this.performSearch();
    }

    /**
     * Виконання пошуку
     */
    performSearch() {
        if (!this.state.searchQuery.trim()) {
            this.loadTreeData();
            return;
        }

        // Автоматично розгортаємо вузли які містять результати пошуку
        const expandMatchingNodes = (nodes) => {
            nodes.forEach(node => {
                const matches = this.nodeMatchesSearch(node, this.state.searchQuery);
                if (matches && node.children && node.children.length > 0) {
                    this.state.expandedNodes.add(node.id);
                }
                if (node.children) {
                    expandMatchingNodes(node.children);
                }
            });
        };

        expandMatchingNodes(this.state.treeData);
    }

    /**
     * Перевірка відповідності вузла пошуковому запиту
     */
    nodeMatchesSearch(node, query) {
        const lowerQuery = query.toLowerCase();
        return node.name.toLowerCase().includes(lowerQuery) ||
               (node.code && node.code.toLowerCase().includes(lowerQuery));
    }

    /**
     * Рендеринг вузла дерева
     */
    renderNode(node, level = 0) {
        const isExpanded = this.state.expandedNodes.has(node.id);
        const isSelected = this.state.selectedNode === node.id;
        const hasChildren = node.children && node.children.length > 0;

        // Перевірка відповідності пошуку
        const matchesSearch = !this.state.searchQuery ||
                             this.nodeMatchesSearch(node, this.state.searchQuery);

        if (!matchesSearch && !this.hasMatchingDescendants(node)) {
            return '';
        }

        return `
            <div class="hierarchy-tree-node ${isSelected ? 'selected' : ''} cbo-type-${node.cbo_type} hierarchy-tree-level-${level}"
                 data-node-id="${node.id}"
                 data-level="${level}"
                 onclick="this.closest('.hierarchy-tree-widget').component.selectNode(${node.id})"
                 ondblclick="this.closest('.hierarchy-tree-widget').component.openNodeForm(${JSON.stringify(node).replace(/"/g, '&quot;')})">
                
                <div class="hierarchy-tree-content">
                    <!-- Toggle button -->
                    <span class="hierarchy-tree-toggle ${hasChildren ? 'has-children' : ''}"
                          onclick="event.stopPropagation(); this.closest('.hierarchy-tree-widget').component.toggleNode(${node.id})">
                        ${hasChildren ? (isExpanded ? '▼' : '▶') : ''}
                    </span>
                    
                    <!-- Іконка -->
                    <span class="hierarchy-tree-icon">
                        <i class="fa ${node.icon || 'fa-folder'} ${node.color_class || 'text-secondary'}"></i>
                    </span>
                    
                    <!-- Назва -->
                    <span class="hierarchy-tree-label" title="${node.name}">
                        ${node.name}
                    </span>
                    
                    <!-- Код ЦБО -->
                    ${node.code ? `<span class="hierarchy-tree-badge badge badge-secondary">${node.code}</span>` : ''}
                    
                    <!-- Метадані -->
                    <div class="hierarchy-tree-meta">
                        ${node.budget_count > 0 ? 
                            `<span class="hierarchy-tree-badge badge badge-info" title="Кількість бюджетів">${node.budget_count} 📊</span>` : ''}
                        ${node.child_count > 0 ? 
                            `<span class="hierarchy-tree-badge badge badge-secondary" title="Дочірні ЦБО">${node.child_count} 🏢</span>` : ''}
                        ${node.execution_rate > 0 ? 
                            `<span class="hierarchy-tree-badge badge badge-${this.getExecutionBadgeClass(node.execution_rate)}" title="Виконання бюджету">${node.execution_rate.toFixed(1)}%</span>` : ''}
                    </div>
                    
                    <!-- Дії -->
                    <div class="hierarchy-tree-actions">
                        ${node.budget_count > 0 ? 
                            `<button class="hierarchy-tree-action btn-tree-primary" 
                                    onclick="event.stopPropagation(); this.closest('.hierarchy-tree-widget').component.viewBudgets(${JSON.stringify(node)})"
                                    title="Переглянути бюджети">📊</button>` : ''}
                        
                        <button class="hierarchy-tree-action btn-tree-success" 
                                onclick="event.stopPropagation(); this.closest('.hierarchy-tree-widget').component.createBudget(${JSON.stringify(node)})"
                                title="Створити бюджет">💰</button>
                                
                        <button class="hierarchy-tree-action btn-tree-secondary" 
                                onclick="event.stopPropagation(); this.closest('.hierarchy-tree-widget').component.createChildNode(${JSON.stringify(node)})"
                                title="Додати підрозділ">➕</button>
                    </div>
                </div>
                
                <!-- Дочірні вузли -->
                ${isExpanded && hasChildren ? 
                    `<div class="hierarchy-tree-children">
                        ${node.children.map(child => this.renderNode(child, level + 1)).join('')}
                     </div>` : ''}
            </div>
        `;
    }

    /**
     * Перевірка наявності відповідних нащадків
     */
    hasMatchingDescendants(node) {
        if (!node.children) return false;

        return node.children.some(child =>
            this.nodeMatchesSearch(child, this.state.searchQuery) ||
            this.hasMatchingDescendants(child)
        );
    }

    /**
     * Отримання CSS класу для badge виконання
     */
    getExecutionBadgeClass(rate) {
        if (rate >= 90) return 'success';
        if (rate >= 70) return 'info';
        if (rate >= 50) return 'warning';
        return 'danger';
    }

    /**
     * Отримання типу дочірнього ЦБО за замовчуванням
     */
    _getDefaultChildType(parentType) {
        const typeHierarchy = {
            'holding': 'enterprise',
            'enterprise': 'business_direction',
            'business_direction': 'department',
            'department': 'division',
            'division': 'office',
            'office': 'team'
        };
        return typeHierarchy[parentType] || 'department';
    }

    /**
     * Отримання рівня бюджетування за замовчуванням
     */
    _getDefaultChildLevel(parentLevel) {
        const levelHierarchy = {
            'strategic': 'tactical',
            'tactical': 'operational',
            'operational': 'functional'
        };
        return levelHierarchy[parentLevel] || 'functional';
    }

    /**
     * Отримання іконки для типу ЦБО
     */
    _getIconForType(cboType) {
        const icons = {
            'holding': 'fa-university',
            'enterprise': 'fa-industry',
            'business_direction': 'fa-building',
            'department': 'fa-building-o',
            'division': 'fa-folder',
            'office': 'fa-briefcase',
            'team': 'fa-users',
            'project': 'fa-tasks'
        };
        return icons[cboType] || 'fa-folder';
    }

    /**
     * Отримання іконки для рівня консолідації
     */
    _getConsolidationIcon(consolidationLevel) {
        const icons = {
            'holding': '🏛️',
            'company': '🏭',
            'department': '📊'
        };
        return icons[consolidationLevel] || '💰';
    }
}

// Реєстрація віджета
registry.category("fields").add("hierarchy_tree", HierarchyTreeWidget);