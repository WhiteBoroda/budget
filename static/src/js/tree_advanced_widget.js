/** @odoo-module **/
// Розширений віджет дерева - ПОВНІСТЮ СУМІСНИЙ З ODOO 17

import { Component, useState, onWillStart, onMounted, useRef } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { debounce } from "@web/core/utils/timing";

/**
 * Розширений віджет дерева для ЦБО з додатковими функціями
 */
export class AdvancedTreeWidget extends Component {
    static template = "budget.AdvancedTreeWidget";
    static props = {
        readonly: { type: Boolean, optional: true },
        record: { type: Object, optional: true },
        value: { type: [Number, Boolean], optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.dialog = useService("dialog");

        this.treeContainerRef = useRef("tree-container");

        this.state = useState({
            treeData: [],
            loading: true,
            selectedNodes: new Set(),
            expandedNodes: new Set(),
            searchQuery: '',
            filteredData: [],
            viewMode: 'tree', // tree, cards, compact, analytics
            showContextMenu: false,
            contextMenuNode: null,
            contextMenuPosition: { x: 0, y: 0 },
            draggedNode: null,
            dropTarget: null,
            showInactive: false,
            showAnalytics: false,
            analyticsData: null
        });

        // Налаштування віджета
        this.settings = {
            enableDragDrop: true,
            enableMultiSelect: true,
            enableContextMenu: true,
            autoSave: true,
            expandOnLoad: false,
            maxNodes: 1000 // Обмеження для продуктивності
        };

        // Debounced функції
        this.searchDebounced = debounce(this.performSearch.bind(this), 300);
        this.saveStateDebounced = debounce(this.saveTreeState.bind(this), 1000);

        onWillStart(async () => {
            await this.loadTreeData();
            this.restoreTreeState();
        });

        onMounted(() => {
            this.setupEventListeners();
            this.setupDragAndDrop();
        });
    }

    /**
     * Завантаження даних дерева з кешуванням
     */
    async loadTreeData(refresh = false) {
        try {
            this.state.loading = true;

            // Спробуємо отримати з кешу, якщо не refresh
            if (!refresh) {
                const cached = this.getCachedData();
                if (cached && cached.timestamp > Date.now() - 300000) { // 5 хвилин
                    this.state.treeData = cached.data;
                    this.state.filteredData = [...this.state.treeData];
                    this.state.loading = false;
                    return;
                }
            }

            const data = await this.orm.call(
                "budget.responsibility.center",
                "get_advanced_tree_data",
                [],
                {
                    include_analytics: this.state.showAnalytics,
                    include_inactive: this.state.showInactive,
                    max_depth: 10
                }
            );

            this.state.treeData = data.tree || [];
            this.state.analyticsData = data.analytics || null;
            this.state.filteredData = [...this.state.treeData];

            // Кешуємо дані
            this.setCachedData(this.state.treeData);

            // Розгортаємо перший рівень за замовчуванням
            if (!refresh && this.settings.expandOnLoad) {
                this.expandFirstLevel();
            }

        } catch (error) {
            this.notification.add(
                "Помилка завантаження розширеного дерева",
                { type: "danger" }
            );
            console.error("Advanced tree loading error:", error);
        } finally {
            this.state.loading = false;
        }
    }

    /**
     * Налаштування обробників подій
     */
    setupEventListeners() {
        // Глобальні обробники
        document.addEventListener('click', this.handleGlobalClick.bind(this));
        document.addEventListener('keydown', this.handleKeydown.bind(this));
        document.addEventListener('contextmenu', this.handleContextMenu.bind(this));

        // Обробка зміни розміру вікна
        window.addEventListener('resize', debounce(this.handleResize.bind(this), 250));
    }

    /**
     * Налаштування drag & drop
     */
    setupDragAndDrop() {
        if (!this.settings.enableDragDrop) return;

        const container = this.treeContainerRef.el;
        if (!container) return;

        container.addEventListener('dragstart', this.handleDragStart.bind(this));
        container.addEventListener('dragover', this.handleDragOver.bind(this));
        container.addEventListener('drop', this.handleDrop.bind(this));
        container.addEventListener('dragend', this.handleDragEnd.bind(this));
    }

    /**
     * Обробка глобального кліку
     */
    handleGlobalClick(event) {
        if (!event.target.closest('.hierarchy-tree-node')) {
            this.state.selectedNodes.clear();
        }

        if (!event.target.closest('.hierarchy-context-menu')) {
            this.state.showContextMenu = false;
        }
    }

    /**
     * Обробка клавіатури
     */
    handleKeydown(event) {
        switch (event.key) {
            case 'Escape':
                this.state.selectedNodes.clear();
                this.state.showContextMenu = false;
                break;
            case 'Delete':
                if (this.state.selectedNodes.size > 0) {
                    this.deleteSelectedNodes();
                }
                break;
            case 'F5':
                event.preventDefault();
                this.refreshTree();
                break;
            case 'a':
                if (event.ctrlKey) {
                    event.preventDefault();
                    this.selectAllNodes();
                }
                break;
        }
    }

    /**
     * Обробка контекстного меню
     */
    handleContextMenu(event) {
        if (!this.settings.enableContextMenu) return;

        const nodeElement = event.target.closest('.hierarchy-tree-node');
        if (!nodeElement) return;

        event.preventDefault();

        const nodeId = parseInt(nodeElement.dataset.nodeId);
        const node = this.findNodeById(nodeId);

        if (node) {
            this.state.contextMenuNode = node;
            this.state.contextMenuPosition = { x: event.clientX, y: event.clientY };
            this.state.showContextMenu = true;
        }
    }

    /**
     * Розширений пошук з фільтрами
     */
    performSearch() {
        if (!this.state.searchQuery.trim()) {
            this.state.filteredData = [...this.state.treeData];
            return;
        }

        const query = this.state.searchQuery.toLowerCase();
        const filters = this.parseSearchQuery(query);

        this.state.filteredData = this.filterTreeNodes(this.state.treeData, filters);
    }

    /**
     * Парсинг запиту пошуку
     */
    parseSearchQuery(query) {
        const filters = {
            text: query,
            type: null,
            hasbudgets: null,
            active: null
        };

        // Парсимо спеціальні фільтри: type:enterprise hasbudgets:true active:false
        const parts = query.split(' ');
        const textParts = [];

        for (const part of parts) {
            if (part.includes(':')) {
                const [key, value] = part.split(':');
                switch (key) {
                    case 'type':
                        filters.type = value;
                        break;
                    case 'hasbudgets':
                        filters.hasbudgets = value === 'true';
                        break;
                    case 'active':
                        filters.active = value === 'true';
                        break;
                    default:
                        textParts.push(part);
                }
            } else {
                textParts.push(part);
            }
        }

        filters.text = textParts.join(' ');
        return filters;
    }

    /**
     * Розширена фільтрація вузлів
     */
    filterTreeNodes(nodes, filters) {
        const filtered = [];

        for (const node of nodes) {
            let matches = true;

            // Текстовий пошук
            if (filters.text) {
                const textMatch = (
                    node.name?.toLowerCase().includes(filters.text) ||
                    node.code?.toLowerCase().includes(filters.text) ||
                    node.type?.toLowerCase().includes(filters.text)
                );
                matches = matches && textMatch;
            }

            // Фільтр по типу
            if (filters.type) {
                matches = matches && node.type === filters.type;
            }

            // Фільтр по наявності бюджетів
            if (filters.hasbudgets !== null) {
                const hasBudgets = (node.budget_count || 0) > 0;
                matches = matches && (hasBudgets === filters.hasbudgets);
            }

            // Фільтр по активності
            if (filters.active !== null) {
                matches = matches && (node.active === filters.active);
            }

            if (matches) {
                filtered.push({
                    ...node,
                    children: node.children || []
                });
            } else if (node.children) {
                const filteredChildren = this.filterTreeNodes(node.children, filters);
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
     * Вибір вузла з підтримкою множинного вибору
     */
    selectNode(node, multiSelect = false) {
        if (!this.settings.enableMultiSelect || !multiSelect) {
            this.state.selectedNodes.clear();
        }

        if (this.state.selectedNodes.has(node.id)) {
            this.state.selectedNodes.delete(node.id);
        } else {
            this.state.selectedNodes.add(node.id);
        }

        this.saveStateDebounced();
    }

    /**
     * Вибір всіх вузлів
     */
    selectAllNodes() {
        const addAllNodes = (nodes) => {
            nodes.forEach(node => {
                this.state.selectedNodes.add(node.id);
                if (node.children) {
                    addAllNodes(node.children);
                }
            });
        };

        addAllNodes(this.state.filteredData);
    }

    /**
     * Масові операції з вибраними вузлами
     */
    async bulkOperation(operation) {
        const selectedNodeIds = Array.from(this.state.selectedNodes);
        if (selectedNodeIds.length === 0) {
            this.notification.add("Виберіть вузли для операції", { type: "warning" });
            return;
        }

        try {
            await this.orm.call(
                "budget.responsibility.center",
                "bulk_operation",
                [selectedNodeIds, operation]
            );

            this.notification.add(
                `Операція "${operation}" виконана для ${selectedNodeIds.length} вузлів`,
                { type: "success" }
            );

            await this.loadTreeData(true);
        } catch (error) {
            this.notification.add(
                `Помилка виконання операції: ${error.message}`,
                { type: "danger" }
            );
        }
    }

    /**
     * Експорт вибраних вузлів
     */
    async exportSelected() {
        const selectedNodeIds = Array.from(this.state.selectedNodes);
        if (selectedNodeIds.length === 0) {
            this.notification.add("Виберіть вузли для експорту", { type: "warning" });
            return;
        }

        try {
            const data = await this.orm.call(
                "budget.responsibility.center",
                "export_nodes",
                [selectedNodeIds]
            );

            this.downloadFile(data, `tree_export_${new Date().toISOString().split('T')[0]}.json`);
        } catch (error) {
            this.notification.add("Помилка експорту", { type: "danger" });
        }
    }

    /**
     * Завантаження файлу
     */
    downloadFile(data, filename) {
        const blob = new Blob([JSON.stringify(data, null, 2)], {
            type: 'application/json'
        });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        a.click();
        URL.revokeObjectURL(url);
    }

    /**
     * Збереження стану дерева
     */
    saveTreeState() {
        const state = {
            expandedNodes: Array.from(this.state.expandedNodes),
            selectedNodes: Array.from(this.state.selectedNodes),
            viewMode: this.state.viewMode,
            searchQuery: this.state.searchQuery
        };

        localStorage.setItem('budget_tree_state', JSON.stringify(state));
    }

    /**
     * Відновлення стану дерева
     */
    restoreTreeState() {
        try {
            const saved = localStorage.getItem('budget_tree_state');
            if (saved) {
                const state = JSON.parse(saved);
                this.state.expandedNodes = new Set(state.expandedNodes || []);
                this.state.selectedNodes = new Set(state.selectedNodes || []);
                this.state.viewMode = state.viewMode || 'tree';
                this.state.searchQuery = state.searchQuery || '';
            }
        } catch (error) {
            console.warn("Could not restore tree state:", error);
        }
    }

    /**
     * Кешування даних
     */
    setCachedData(data) {
        try {
            const cached = {
                data: data,
                timestamp: Date.now()
            };
            localStorage.setItem('budget_tree_cache', JSON.stringify(cached));
        } catch (error) {
            console.warn("Could not cache tree data:", error);
        }
    }

    /**
     * Отримання кешованих даних
     */
    getCachedData() {
        try {
            const cached = localStorage.getItem('budget_tree_cache');
            return cached ? JSON.parse(cached) : null;
        } catch (error) {
            console.warn("Could not get cached tree data:", error);
            return null;
        }
    }

    /**
     * Пошук вузла по ID
     */
    findNodeById(id, nodes = this.state.treeData) {
        for (const node of nodes) {
            if (node.id === id) {
                return node;
            }
            if (node.children) {
                const found = this.findNodeById(id, node.children);
                if (found) return found;
            }
        }
        return null;
    }

    /**
     * Аналітика дерева
     */
    async loadAnalytics() {
        try {
            this.state.showAnalytics = true;
            const analytics = await this.orm.call(
                "budget.responsibility.center",
                "get_tree_analytics",
                []
            );
            this.state.analyticsData = analytics;
        } catch (error) {
            this.notification.add("Помилка завантаження аналітики", { type: "danger" });
        }
    }

    /**
     * Оптимізація дерева
     */
    async optimizeTree() {
        return this.action.doAction({
            name: "Оптимізація структури дерева",
            type: "ir.actions.act_window",
            res_model: "tree.optimization.wizard",
            view_mode: "form",
            target: "new"
        });
    }

    /**
     * Обробка зміни розміру
     */
    handleResize() {
        // Адаптивні зміни інтерфейсу
        const container = this.treeContainerRef.el;
        if (container && window.innerWidth < 768) {
            this.state.viewMode = 'compact';
        }
    }

    /**
     * Очищення пам'яті при знищенні
     */
    willUnmount() {
        document.removeEventListener('click', this.handleGlobalClick);
        document.removeEventListener('keydown', this.handleKeydown);
        document.removeEventListener('contextmenu', this.handleContextMenu);
        window.removeEventListener('resize', this.handleResize);
    }
}

// Реєстрація розширеного віджета
registry.category("fields").add("advanced_tree_widget", AdvancedTreeWidget);