/** @odoo-module **/

import { Component, useState, onWillStart, onMounted, useRef } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { debounce } from "@web/core/utils/timing";

/**
 * Розширений віджет дерева для ЦБО - ПОВНІСТЮ СУМІСНИЙ З ODOO 17
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
            viewMode: 'tree', // tree, cards, compact
            showContextMenu: false,
            contextMenuNode: null,
            contextMenuPosition: { x: 0, y: 0 },
            draggedNode: null,
            dropTarget: null
        });

        // Налаштування віджета
        this.settings = {
            enableDragDrop: true,
            enableMultiSelect: true,
            enableContextMenu: true,
            autoSave: true,
            expandOnLoad: false
        };

        // Debounced пошук
        this.searchDebounced = debounce(this.performSearch.bind(this), 300);

        onWillStart(async () => {
            await this.loadTreeData();
            this.restoreTreeState();
        });

        onMounted(() => {
            this.setupEventListeners();
        });
    }

    /**
     * Завантаження даних дерева
     */
    async loadTreeData(refresh = false) {
        try {
            this.state.loading = true;

            const data = await this.orm.call(
                "budget.responsibility.center",
                "get_hierarchy_tree",
                [],
                { context: { tree_view: true } }
            );

            this.state.treeData = this._processTreeData(data);

            if (this.settings.expandOnLoad || refresh) {
                this._autoExpandImportantNodes();
            }

        } catch (error) {
            this.notification.add("Помилка завантаження дерева", { type: "danger" });
            console.error("Advanced tree loading error:", error);
        } finally {
            this.state.loading = false;
        }
    }

    /**
     * Обробка даних дерева
     */
    _processTreeData(data) {
        return data.map(node => this._enrichNode(node));
    }

    /**
     * Збагачення вузла додатковими властивостями
     */
    _enrichNode(node) {
        return {
            ...node,
            expanded: this.state.expandedNodes.has(node.id),
            selected: this.state.selectedNodes.has(node.id),
            children: node.children ? node.children.map(child => this._enrichNode(child)) : []
        };
    }

    /**
     * Автоматичне розгортання важливих вузлів
     */
    _autoExpandImportantNodes() {
        const expandImportantNodes = (nodes) => {
            nodes.forEach(node => {
                // Розгортаємо вузли з бюджетами або багатьма дочірніми елементами
                if (node.budget_count > 0 || node.child_count > 3) {
                    this.state.expandedNodes.add(node.id);
                }

                if (node.children) {
                    expandImportantNodes(node.children);
                }
            });
        };

        expandImportantNodes(this.state.treeData);
    }

    /**
     * Налаштування обробників подій
     */
    setupEventListeners() {
        document.addEventListener('click', this._handleDocumentClick.bind(this));
        document.addEventListener('keydown', this._handleKeyDown.bind(this));

        // Drag & Drop якщо увімкнено
        if (this.settings.enableDragDrop) {
            this._setupDragAndDrop();
        }
    }

    /**
     * Перемикання розгортання вузла
     */
    toggleNode(nodeId) {
        if (this.state.expandedNodes.has(nodeId)) {
            this.state.expandedNodes.delete(nodeId);
        } else {
            this.state.expandedNodes.add(nodeId);
        }

        if (this.settings.autoSave) {
            this._saveTreeState();
        }
    }

    /**
     * Виділення вузла
     */
    selectNode(nodeId, multiSelect = false) {
        if (multiSelect && this.settings.enableMultiSelect) {
            if (this.state.selectedNodes.has(nodeId)) {
                this.state.selectedNodes.delete(nodeId);
            } else {
                this.state.selectedNodes.add(nodeId);
            }
        } else {
            this.state.selectedNodes.clear();
            this.state.selectedNodes.add(nodeId);
        }
    }

    /**
     * Показ контекстного меню
     */
    showContextMenu(event, nodeId) {
        if (!this.settings.enableContextMenu) return;

        event.preventDefault();

        this.state.contextMenuNode = this._findNodeById(nodeId);
        this.state.contextMenuPosition = { x: event.clientX, y: event.clientY };
        this.state.showContextMenu = true;
    }

    /**
     * Дії контекстного меню
     */
    async contextMenuAction(action) {
        const node = this.state.contextMenuNode;
        this.hideContextMenu();

        switch (action) {
            case 'view':
                await this._openNodeForm(node);
                break;
            case 'edit':
                await this._editNode(node);
                break;
            case 'create_child':
                await this._createChildNode(node);
                break;
            case 'create_budget':
                await this._createBudget(node);
                break;
            case 'view_budgets':
                await this._viewBudgets(node);
                break;
            case 'clone':
                await this._cloneNode(node);
                break;
            case 'export':
                await this._exportSubtree(node);
                break;
            case 'delete':
                await this._deleteNode(node);
                break;
        }
    }

    /**
     * Відкриття форми ЦБО
     */
    async _openNodeForm(node) {
        const action = {
            type: 'ir.actions.act_window',
            res_model: 'budget.responsibility.center',
            res_id: node.id,
            view_mode: 'form',
            target: 'new',
            context: { tree_view: true }
        };
        this.action.doAction(action);
    }

    /**
     * Редагування вузла
     */
    async _editNode(node) {
        await this._openNodeForm(node);
    }

    /**
     * Створення дочірнього вузла
     */
    async _createChildNode(parentNode) {
        const action = {
            type: 'ir.actions.act_window',
            res_model: 'budget.responsibility.center',
            view_mode: 'form',
            context: {
                default_parent_id: parentNode.id,
                default_cbo_type: this._getDefaultChildType(parentNode.cbo_type),
                default_budget_level: this._getDefaultChildLevel(parentNode.budget_level),
                tree_view: true
            },
            target: 'new'
        };
        this.action.doAction(action);
    }

    /**
     * Створення бюджету
     */
    async _createBudget(node) {
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
     * Перегляд бюджетів
     */
    async _viewBudgets(node) {
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
     * Клонування вузла
     */
    async _cloneNode(node) {
        try {
            await this.orm.call(
                "budget.responsibility.center",
                "copy",
                [node.id],
                {
                    context: {
                        default_name: `${node.name} (копія)`,
                        default_code: `${node.code}_copy`
                    }
                }
            );

            this.notification.add("Вузол успішно скопійовано", { type: "success" });
            await this.loadTreeData(true);
        } catch (error) {
            this.notification.add("Помилка копіювання вузла", { type: "danger" });
        }
    }

    /**
     * Видалення вузла
     */
    async _deleteNode(node) {
        if (node.child_count > 0) {
            this.notification.add(
                "Неможливо видалити ЦБО з дочірніми підрозділами",
                { type: "warning" }
            );
            return;
        }

        const confirmed = await this.dialog.add({
            title: "Підтвердження видалення",
            body: `Ви впевнені, що хочете видалити ЦБО "${node.name}"?`,
            confirmLabel: "Видалити",
            cancelLabel: "Скасувати"
        });

        if (confirmed) {
            try {
                await this.orm.unlink("budget.responsibility.center", [node.id]);
                this.notification.add("ЦБО успішно видалено", { type: "success" });
                await this.loadTreeData(true);
            } catch (error) {
                this.notification.add("Помилка видалення ЦБО", { type: "danger" });
            }
        }
    }

    /**
     * Пошук в дереві
     */
    performSearch() {
        if (!this.state.searchQuery.trim()) {
            this.loadTreeData();
            return;
        }

        // Фільтруємо дерево
        const filteredData = this._filterTreeData(this.state.treeData, this.state.searchQuery);
        this.state.treeData = filteredData;

        // Автоматично розгортаємо знайдені вузли
        this._expandSearchResults(filteredData);
    }

    /**
     * Фільтрація дерева
     */
    _filterTreeData(nodes, query) {
        const lowerQuery = query.toLowerCase();

        return nodes.filter(node => {
            const matchesNode = node.name.toLowerCase().includes(lowerQuery) ||
                               (node.code && node.code.toLowerCase().includes(lowerQuery));

            const hasMatchingChildren = node.children &&
                                      this._filterTreeData(node.children, query).length > 0;

            if (hasMatchingChildren) {
                node.children = this._filterTreeData(node.children, query);
            }

            return matchesNode || hasMatchingChildren;
        });
    }

    /**
     * Розгортання результатів пошуку
     */
    _expandSearchResults(nodes) {
        nodes.forEach(node => {
            if (node.children && node.children.length > 0) {
                this.state.expandedNodes.add(node.id);
                this._expandSearchResults(node.children);
            }
        });
    }

    /**
     * Знайти вузол по ID
     */
    _findNodeById(nodeId, nodes = null) {
        nodes = nodes || this.state.treeData;

        for (const node of nodes) {
            if (node.id === nodeId) {
                return node;
            }
            if (node.children) {
                const found = this._findNodeById(nodeId, node.children);
                if (found) return found;
            }
        }
        return null;
    }

    /**
     * Збереження стану дерева
     */
    _saveTreeState() {
        const state = {
            expandedNodes: Array.from(this.state.expandedNodes),
            selectedNodes: Array.from(this.state.selectedNodes),
            viewMode: this.state.viewMode
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
            }
        } catch (error) {
            console.warn('Не вдалося відновити стан дерева:', error);
        }
    }

    /**
     * Створення кореневого вузла
     */
    async _createRootNode() {
        const action = {
            type: 'ir.actions.act_window',
            res_model: 'budget.responsibility.center',
            view_mode: 'form',
            context: {
                default_cbo_type: 'holding',
                default_budget_level: 'strategic',
                tree_view: true
            },
            target: 'new'
        };
        this.action.doAction(action);
    }

    /**
     * Налаштування Drag & Drop
     */
    _setupDragAndDrop() {
        // Буде реалізовано при потребі
    }

    /**
     * Приховування контекстного меню
     */
    hideContextMenu() {
        this.state.showContextMenu = false;
        this.state.contextMenuNode = null;
    }

    /**
     * Обробка кліків по документу
     */
    _handleDocumentClick(event) {
        // Приховування контекстного меню
        if (this.state.showContextMenu && !event.target.closest('.context-menu')) {
            this.hideContextMenu();
        }
    }

    /**
     * Обробка клавіатури
     */
    _handleKeyDown(event) {
        if (!this.state.selectedNodes.size) return;

        switch (event.key) {
            case 'Delete':
                this._deleteSelectedNodes();
                break;
            case 'Enter':
                this._editSelectedNode();
                break;
            case 'ArrowUp':
                event.preventDefault();
                this._navigateUp();
                break;
            case 'ArrowDown':
                event.preventDefault();
                this._navigateDown();
                break;
            case 'ArrowRight':
                this._expandSelectedNode();
                break;
            case 'ArrowLeft':
                this._collapseSelectedNode();
                break;
            case 'F2':
                event.preventDefault();
                this._renameSelectedNode();
                break;
        }
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
     * Експорт піддерева
     */
    async _exportSubtree(node) {
        try {
            await this.orm.call('budget.responsibility.center', 'action_export_tree_structure', [node.id]);
            this.notification.add("Структуру експортовано успішно", { type: "success" });
        } catch (error) {
            this.notification.add("Помилка експорту структури", { type: "danger" });
        }
    }

    /**
     * Публічні методи для зовнішнього API
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

    collapseAll() {
        this.state.expandedNodes.clear();
    }

    setViewMode(mode) {
        this.state.viewMode = mode;
        if (this.settings.autoSave) {
            this._saveTreeState();
        }
    }

    getSelectedNodes() {
        return Array.from(this.state.selectedNodes)
            .map(id => this._findNodeById(id))
            .filter(Boolean);
    }

    selectNodeById(nodeId) {
        this.selectNode(nodeId, false);
    }

    searchInTree(query) {
        this.state.searchQuery = query;
        this.performSearch();
    }
}

// Шаблон для AdvancedTreeWidget
AdvancedTreeWidget.template = "budget.AdvancedTreeWidget";

// Реєстрація компонента
registry.category("fields").add("advanced_tree", AdvancedTreeWidget);

export default AdvancedTreeWidget;