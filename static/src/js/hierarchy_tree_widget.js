/** @odoo-module **/
// Віджет ієрархічного дерева для ЦБО - ПОВНІСТЮ СУМІСНИЙ З ODOO 17

import { Component, useState, onWillStart, onMounted, useRef } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { debounce } from "@web/core/utils/timing";

/**
 * Віджет ієрархічного дерева для ЦБО
 */
export class HierarchyTreeWidget extends Component {
    static template = "budget.HierarchyTreeWidget";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.dialog = useService("dialog");

        this.treeRef = useRef("tree-container");

        this.state = useState({
            treeData: [],
            loading: true,
            selectedNode: null,
            expandedNodes: new Set(),
            searchQuery: '',
            filteredData: [],
            showInactive: false,
            viewMode: 'tree' // tree, compact, cards
        });

        // Debounced пошук
        this.searchDebounced = debounce(this.performSearch.bind(this), 300);

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

            this.state.treeData = data || [];
            this.state.filteredData = [...this.state.treeData];

            // Розгортаємо перший рівень за замовчуванням
            this.expandFirstLevel();

        } catch (error) {
            this.notification.add(
                "Помилка завантаження дерева ієрархії",
                { type: "danger" }
            );
            console.error("Tree loading error:", error);
        } finally {
            this.state.loading = false;
        }
    }

    /**
     * Налаштування обробників подій
     */
    setupEventListeners() {
        // Клік по документу для зняття виділення
        document.addEventListener('click', (event) => {
            if (!event.target.closest('.hierarchy-tree-node')) {
                this.state.selectedNode = null;
            }
        });

        // Обробка клавіатури
        document.addEventListener('keydown', (event) => {
            if (event.key === 'Escape') {
                this.state.selectedNode = null;
            }
        });
    }

    /**
     * Розгортання першого рівня
     */
    expandFirstLevel() {
        this.state.treeData.forEach(node => {
            if (node.children && node.children.length > 0) {
                this.state.expandedNodes.add(node.id);
            }
        });
    }

    /**
     * Обробка вводу пошуку
     */
    onSearchInput(event) {
        this.state.searchQuery = event.target.value;
        this.searchDebounced();
    }

    /**
     * Виконання пошуку
     */
    performSearch() {
        if (!this.state.searchQuery.trim()) {
            this.state.filteredData = [...this.state.treeData];
            return;
        }

        const query = this.state.searchQuery.toLowerCase();
        this.state.filteredData = this.filterTreeNodes(this.state.treeData, query);
    }

    /**
     * Фільтрація вузлів дерева
     */
    filterTreeNodes(nodes, query) {
        const filtered = [];

        for (const node of nodes) {
            const matches = (
                node.name?.toLowerCase().includes(query) ||
                node.code?.toLowerCase().includes(query) ||
                node.type?.toLowerCase().includes(query)
            );

            if (matches) {
                // Якщо вузол відповідає, додаємо його з усіма дочірніми
                filtered.push({
                    ...node,
                    children: node.children || []
                });
            } else if (node.children) {
                // Рекурсивно перевіряємо дочірні вузли
                const filteredChildren = this.filterTreeNodes(node.children, query);
                if (filteredChildren.length > 0) {
                    filtered.push({
                        ...node,
                        children: filteredChildren
                    });
                }
            }
        }

        return filtered;
    }

    /**
     * Перемикання розгортання вузла
     */
    toggleExpand(nodeId) {
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
        this.state.selectedNode = node;
    }

    /**
     * Розгортання всіх вузлів
     */
    expandAll() {
        const addAllNodes = (nodes) => {
            nodes.forEach(node => {
                this.state.expandedNodes.add(node.id);
                if (node.children) {
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
     * Перемикання показу неактивних
     */
    toggleInactive() {
        this.state.showInactive = !this.state.showInactive;
        this.performSearch(); // Перефільтруємо дані
    }

    /**
     * Зміна режиму перегляду
     */
    changeViewMode(mode) {
        this.state.viewMode = mode;
    }

    /**
     * Перегляд бюджетів для вузла
     */
    async viewBudgets(node) {
        return this.action.doAction({
            name: `Бюджети - ${node.name}`,
            type: "ir.actions.act_window",
            res_model: "budget.plan",
            view_mode: "tree,form",
            domain: [['cbo_id', '=', node.id]],
            context: {
                default_cbo_id: node.id,
                search_default_group_by_period: 1
            }
        });
    }

    /**
     * Створення нового бюджету
     */
    async createBudget(node) {
        return this.action.doAction({
            name: `Новий бюджет - ${node.name}`,
            type: "ir.actions.act_window",
            res_model: "budget.plan",
            view_mode: "form",
            context: {
                default_cbo_id: node.id,
                default_name: `Бюджет ${node.name}`
            },
            target: "new"
        });
    }

    /**
     * Редагування ЦБО
     */
    async editCbo(node) {
        return this.action.doAction({
            name: `Редагувати - ${node.name}`,
            type: "ir.actions.act_window",
            res_model: "budget.responsibility.center",
            res_id: node.id,
            view_mode: "form",
            views: [[false, "form"]],
            target: "new"
        });
    }

    /**
     * Створення дочірнього ЦБО
     */
    async createChildCbo(node) {
        return this.action.doAction({
            name: `Новий підрозділ - ${node.name}`,
            type: "ir.actions.act_window",
            res_model: "budget.responsibility.center",
            view_mode: "form",
            context: {
                default_parent_id: node.id,
                default_name: `Підрозділ ${node.name}`
            },
            target: "new"
        });
    }

    /**
     * Отримання CSS класу для вузла
     */
    getNodeClass(node) {
        let classes = ['hierarchy-tree-node'];

        if (this.state.selectedNode?.id === node.id) {
            classes.push('selected');
        }

        if (node.children && node.children.length > 0) {
            classes.push('has-children');
        }

        if (!node.active) {
            classes.push('inactive');
        }

        if (node.type) {
            classes.push(`cbo-type-${node.type}`);
        }

        return classes.join(' ');
    }

    /**
     * Отримання іконки для вузла
     */
    getNodeIcon(node) {
        const iconMap = {
            holding: 'fa fa-university',
            cluster: 'fa fa-cubes',
            business_direction: 'fa fa-compass',
            brand: 'fa fa-tags',
            enterprise: 'fa fa-industry',
            department: 'fa fa-building',
            division: 'fa fa-sitemap',
            office: 'fa fa-briefcase',
            team: 'fa fa-users',
            project: 'fa fa-project-diagram',
            other: 'fa fa-folder'
        };

        return iconMap[node.type] || 'fa fa-folder';
    }

    /**
     * Перевірка чи розгорнутий вузол
     */
    isExpanded(nodeId) {
        return this.state.expandedNodes.has(nodeId);
    }

    /**
     * Оновлення дерева
     */
    async refreshTree() {
        await this.loadTreeData();
        this.notification.add("Дерево оновлено", { type: "success" });
    }

    /**
     * Експорт дерева
     */
    async exportTree() {
        try {
            const data = await this.orm.call(
                "budget.responsibility.center",
                "export_tree_structure",
                []
            );

            // Створюємо та завантажуємо файл
            const blob = new Blob([JSON.stringify(data, null, 2)], {
                type: 'application/json'
            });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `tree_structure_${new Date().toISOString().split('T')[0]}.json`;
            a.click();
            URL.revokeObjectURL(url);

            this.notification.add("Структуру експортовано", { type: "success" });
        } catch (error) {
            this.notification.add("Помилка експорту", { type: "danger" });
        }
    }
}

// Реєстрація віджета
registry.category("fields").add("hierarchy_tree_widget", HierarchyTreeWidget);