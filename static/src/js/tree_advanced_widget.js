/** @odoo-module **/

import { Component, useState, onMounted, onWillUnmount, useRef } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { debounce } from "@web/core/utils/timing";

/**
 * Розширений віджет дерева з drag&drop та покращеною функціональністю
 */
export class AdvancedTreeWidget extends Component {
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.dialog = useService("dialog");
        this.notification = useService("notification");

        this.treeRef = useRef("tree-container");

        this.state = useState({
            treeData: [],
            expandedNodes: new Set(),
            selectedNodes: new Set(),
            draggedNode: null,
            searchQuery: '',
            filterType: 'all',
            loading: true,
            isDragMode: false,
            contextMenuNode: null,
            contextMenuPosition: { x: 0, y: 0 },
            showContextMenu: false,
            viewMode: 'tree', // tree, cards, compact
        });

        // Налаштування
        this.settings = {
            enableDragDrop: true,
            enableMultiSelect: true,
            enableContextMenu: true,
            enableSearch: true,
            enableVirtualScroll: false,
            autoSave: true,
            animationDuration: 300
        };

        // Кешування
        this.cache = new Map();
        this.searchDebounced = debounce(this._performSearch.bind(this), 300);

        onMounted(() => {
            this.loadTreeData();
            this._setupEventListeners();
        });

        onWillUnmount(() => {
            this._removeEventListeners();
        });
    }

    /**
     * Завантаження даних дерева з кешуванням
     */
    async loadTreeData(forceReload = false) {
        const cacheKey = `tree_data_${this.props.modelName || 'default'}`;

        if (!forceReload && this.cache.has(cacheKey)) {
            this.state.treeData = this.cache.get(cacheKey);
            this.state.loading = false;
            return;
        }

        try {
            this.state.loading = true;

            const model = this.props.modelName || 'budget.responsibility.center';
            const method = this.props.dataMethod || 'get_tree_data';

            const data = await this.orm.call(model, method, [], {
                context: this.props.context || {}
            });

            this.state.treeData = this._processTreeData(data);
            this.cache.set(cacheKey, this.state.treeData);
            this.state.loading = false;

        } catch (error) {
            console.error("Помилка завантаження дерева:", error);
            this.notification.add("Помилка завантаження дерева структури", { type: "danger" });
            this.state.loading = false;
        }
    }

    /**
     * Обробка даних дерева
     */
    _processTreeData(rawData) {
        return rawData.map(item => ({
            ...item,
            expanded: this.state.expandedNodes.has(item.id),
            selected: this.state.selectedNodes.has(item.id),
            children: item.children ? this._processTreeData(item.children) : []
        }));
    }

    /**
     * Налаштування слухачів подій
     */
    _setupEventListeners() {
        document.addEventListener('click', this._handleDocumentClick.bind(this));
        document.addEventListener('keydown', this._handleKeyDown.bind(this));

        if (this.settings.enableDragDrop) {
            this._setupDragDropListeners();
        }
    }

    /**
     * Видалення слухачів подій
     */
    _removeEventListeners() {
        document.removeEventListener('click', this._handleDocumentClick.bind(this));
        document.removeEventListener('keydown', this._handleKeyDown.bind(this));
    }

    /**
     * Налаштування drag & drop
     */
    _setupDragDropListeners() {
        const container = this.treeRef.el;
        if (!container) return;

        container.addEventListener('dragstart', this._handleDragStart.bind(this));
        container.addEventListener('dragover', this._handleDragOver.bind(this));
        container.addEventListener('dragenter', this._handleDragEnter.bind(this));
        container.addEventListener('dragleave', this._handleDragLeave.bind(this));
        container.addEventListener('drop', this._handleDrop.bind(this));
        container.addEventListener('dragend', this._handleDragEnd.bind(this));
    }

    /**
     * Обробка початку перетягування
     */
    _handleDragStart(event) {
        const nodeElement = event.target.closest('.tree-node');
        if (!nodeElement) return;

        const nodeId = parseInt(nodeElement.dataset.nodeId);
        const node = this._findNodeById(nodeId);

        if (!node) return;

        this.state.draggedNode = node;
        this.state.isDragMode = true;

        event.dataTransfer.effectAllowed = 'move';
        event.dataTransfer.setData('text/plain', nodeId);

        // Візуальні ефекти
        nodeElement.classList.add('dragging');
        this._addDropZones();
    }

    /**
     * Обробка перетягування над елементом
     */
    _handleDragOver(event) {
        event.preventDefault();
        event.dataTransfer.dropEffect = 'move';

        const dropZone = event.target.closest('.drop-zone');
        if (dropZone) {
            dropZone.classList.add('drag-over');
        }
    }

    /**
     * Обробка входу в зону перетягування
     */
    _handleDragEnter(event) {
        event.preventDefault();
        const dropZone = event.target.closest('.drop-zone');
        if (dropZone) {
            dropZone.classList.add('drag-enter');
        }
    }

    /**
     * Обробка виходу з зони перетягування
     */
    _handleDragLeave(event) {
        const dropZone = event.target.closest('.drop-zone');
        if (dropZone && !dropZone.contains(event.relatedTarget)) {
            dropZone.classList.remove('drag-over', 'drag-enter');
        }
    }

    /**
     * Обробка скидання елемента
     */
    async _handleDrop(event) {
        event.preventDefault();

        const dropZone = event.target.closest('.drop-zone');
        if (!dropZone || !this.state.draggedNode) return;

        const targetNodeId = parseInt(dropZone.dataset.nodeId);
        const sourceNode = this.state.draggedNode;

        if (targetNodeId === sourceNode.id) return;

        try {
            // Валідація переміщення
            if (this._wouldCreateCycle(sourceNode.id, targetNodeId)) {
                this.notification.add("Неможливо перемістити: створить циклічну залежність", { type: "warning" });
                return;
            }

            // Виконуємо переміщення на сервері
            await this._moveNodeToParent(sourceNode.id, targetNodeId);

            // Оновлюємо дерево
            await this.loadTreeData(true);

            this.notification.add(`${sourceNode.name} переміщено успішно`, { type: "success" });

        } catch (error) {
            console.error("Помилка переміщення:", error);
            this.notification.add("Помилка переміщення елемента", { type: "danger" });
        }

        this._removeDropZones();
    }

    /**
     * Обробка завершення перетягування
     */
    _handleDragEnd(event) {
        this.state.draggedNode = null;
        this.state.isDragMode = false;

        // Очищення візуальних ефектів
        const draggedElement = event.target.closest('.tree-node');
        if (draggedElement) {
            draggedElement.classList.remove('dragging');
        }

        this._removeDropZones();
    }

    /**
     * Додавання зон перетягування
     */
    _addDropZones() {
        const nodes = this.treeRef.el.querySelectorAll('.tree-node');
        nodes.forEach(node => {
            const nodeId = parseInt(node.dataset.nodeId);
            if (nodeId !== this.state.draggedNode.id) {
                node.classList.add('drop-zone');
                node.dataset.nodeId = nodeId;
            }
        });
    }

    /**
     * Видалення зон перетягування
     */
    _removeDropZones() {
        const dropZones = this.treeRef.el.querySelectorAll('.drop-zone');
        dropZones.forEach(zone => {
            zone.classList.remove('drop-zone', 'drag-over', 'drag-enter');
        });
    }

    /**
     * Перевірка на циклічну залежність
     */
    _wouldCreateCycle(sourceId, targetId) {
        const findNode = (nodes, id) => {
            for (const node of nodes) {
                if (node.id === id) return node;
                const found = findNode(node.children || [], id);
                if (found) return found;
            }
            return null;
        };

        const isDescendant = (parentNode, childId) => {
            if (!parentNode.children) return false;

            for (const child of parentNode.children) {
                if (child.id === childId) return true;
                if (isDescendant(child, childId)) return true;
            }
            return false;
        };

        const sourceNode = findNode(this.state.treeData, sourceId);
        return sourceNode ? isDescendant(sourceNode, targetId) : false;
    }

    /**
     * Переміщення вузла на сервері
     */
    async _moveNodeToParent(sourceId, targetId) {
        return await this.orm.write('budget.responsibility.center', [sourceId], {
            parent_id: targetId
        });
    }

    /**
     * Пошук вузла по ID
     */
    _findNodeById(id, nodes = null) {
        const searchNodes = nodes || this.state.treeData;

        for (const node of searchNodes) {
            if (node.id === id) return node;

            if (node.children) {
                const found = this._findNodeById(id, node.children);
                if (found) return found;
            }
        }

        return null;
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

        // Оновлюємо дерево
        this.state.treeData = this._processTreeData(this.state.treeData);

        // Зберігаємо стан в localStorage
        if (this.settings.autoSave) {
            this._saveTreeState();
        }
    }

    /**
     * Вибір вузла
     */
    selectNode(nodeId, isCtrlClick = false) {
        if (this.settings.enableMultiSelect && isCtrlClick) {
            // Множинний вибір
            if (this.state.selectedNodes.has(nodeId)) {
                this.state.selectedNodes.delete(nodeId);
            } else {
                this.state.selectedNodes.add(nodeId);
            }
        } else {
            // Одиночний вибір
            this.state.selectedNodes.clear();
            this.state.selectedNodes.add(nodeId);
        }

        // Оновлюємо дерево
        this.state.treeData = this._processTreeData(this.state.treeData);

        // Викликаємо callback
        if (this.props.onNodeSelect) {
            const selectedNodes = Array.from(this.state.selectedNodes)
                .map(id => this._findNodeById(id))
                .filter(Boolean);
            this.props.onNodeSelect(selectedNodes);
        }
    }

    /**
     * Контекстне меню
     */
    showContextMenu(event, nodeId) {
        if (!this.settings.enableContextMenu) return;

        event.preventDefault();
        event.stopPropagation();

        this.state.contextMenuNode = this._findNodeById(nodeId);
        this.state.contextMenuPosition = { x: event.clientX, y: event.clientY };
        this.state.showContextMenu = true;
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
     * Пошук
     */
    _performSearch() {
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
     * Дії контекстного меню
     */
    async contextMenuAction(action) {
        const node = this.state.contextMenuNode;
        if (!node) return;

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
            case 'delete':
                await this._deleteNode(node);
                break;
            case 'export':
                await this._exportSubtree(node);
                break;
        }
    }

    /**
     * Відкриття форми вузла
     */
    async _openNodeForm(node) {
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
     * Створення дочірнього вузла
     */
    async _createChildNode(node) {
        await this.action.doAction({
            type: 'ir.actions.act_window',
            name: `Новий підрозділ для ${node.name}`,
            res_model: 'budget.responsibility.center',
            view_mode: 'form',
            target: 'new',
            context: {
                default_parent_id: node.id,
                default_cbo_type: this._getDefaultChildType(node.cbo_type),
                default_budget_level: this._getDefaultChildLevel(node.budget_level)
            }
        });
    }

    /**
     * Створення бюджету
     */
    async _createBudget(node) {
        await this.action.doAction({
            type: 'ir.actions.act_window',
            name: `Новий бюджет: ${node.name}`,
            res_model: 'budget.plan',
            view_mode: 'form',
            target: 'new',
            context: {
                default_cbo_id: node.id,
                default_responsible_user_id: node.responsible_user_id
            }
        });
    }

    /**
     * Перегляд бюджетів
     */
    async _viewBudgets(node) {
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
     * Збереження стану дерева
     */
    _saveTreeState() {
        const state = {
            expandedNodes: Array.from(this.state.expandedNodes),
            selectedNodes: Array.from(this.state.selectedNodes),
            viewMode: this.state.viewMode
        };

        localStorage.setItem(`tree_state_${this.props.treeId || 'default'}`, JSON.stringify(state));
    }

    /**
     * Завантаження стану дерева
     */
    _loadTreeState() {
        const saved = localStorage.getItem(`tree_state_${this.props.treeId || 'default'}`);
        if (saved) {
            try {
                const state = JSON.parse(saved);
                this.state.expandedNodes = new Set(state.expandedNodes || []);
                this.state.selectedNodes = new Set(state.selectedNodes || []);
                this.state.viewMode = state.viewMode || 'tree';
            } catch (error) {
                console.warn("Помилка завантаження стану дерева:", error);
            }
        }
    }

    /**
     * Отримання типу дочірнього ЦБО за замовчуванням
     */
    _getDefaultChildType(parentType) {
        const typeHierarchy = {
            'holding': 'enterprise',
            'enterprise': 'department',
            'business_direction': 'department',
            'department': 'office',
            'division': 'office',
            'office': 'team'
        };

        return typeHierarchy[parentType] || 'office';
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
     * Рендеринг дерева
     */
    render() {
        if (this.state.loading) {
            return this._renderLoading();
        }

        return this._renderTree();
    }

    _renderLoading() {
        return `
            <div class="advanced-tree-widget loading">
                <div class="tree-loading">
                    <i class="fa fa-spinner fa-spin fa-2x"></i>
                    <p>Завантаження структури...</p>
                </div>
            </div>
        `;
    }

    _renderTree() {
        return `
            <div class="advanced-tree-widget" data-component="this">
                ${this._renderToolbar()}
                ${this._renderTreeContainer()}
                ${this._renderContextMenu()}
            </div>
        `;
    }

    _renderToolbar() {
        return `
            <div class="tree-toolbar">
                <div class="toolbar-left">
                    <div class="search-container">
                        <input type="text" 
                               class="tree-search" 
                               placeholder="🔍 Пошук в дереві..."
                               value="${this.state.searchQuery}"
                               onkeyup="this.closest('.advanced-tree-widget').component.searchDebounced(event.target.value)">
                    </div>
                    <div class="view-mode-selector">
                        <button class="btn btn-sm ${this.state.viewMode === 'tree' ? 'btn-primary' : 'btn-outline-primary'}"
                                onclick="this.closest('.advanced-tree-widget').component.setViewMode('tree')">
                            🌳 Дерево
                        </button>
                        <button class="btn btn-sm ${this.state.viewMode === 'cards' ? 'btn-primary' : 'btn-outline-primary'}"
                                onclick="this.closest('.advanced-tree-widget').component.setViewMode('cards')">
                            🎴 Картки
                        </button>
                    </div>
                </div>
                
                <div class="toolbar-right">
                    <button class="btn btn-sm btn-outline-secondary"
                            onclick="this.closest('.advanced-tree-widget').component.expandAll()"
                            title="Розгорнути все">
                        ⬇️
                    </button>
                    <button class="btn btn-sm btn-outline-secondary"
                            onclick="this.closest('.advanced-tree-widget').component.collapseAll()"
                            title="Згорнути все">
                        ⬆️
                    </button>
                    <button class="btn btn-sm btn-outline-primary"
                            onclick="this.closest('.advanced-tree-widget').component.loadTreeData(true)"
                            title="Оновити">
                        🔄
                    </button>
                </div>
            </div>
        `;
    }

    _renderTreeContainer() {
        return `
            <div class="tree-container" ref="tree-container">
                ${this.state.treeData.map(node => this._renderNode(node, 0)).join('')}
                ${this.state.treeData.length === 0 ? this._renderEmptyState() : ''}
            </div>
        `;
    }

    _renderNode(node, level) {
        const isExpanded = this.state.expandedNodes.has(node.id);
        const isSelected = this.state.selectedNodes.has(node.id);
        const hasChildren = node.children && node.children.length > 0;

        return `
            <div class="tree-node ${isSelected ? 'selected' : ''} ${this.state.viewMode}" 
                 data-node-id="${node.id}"
                 data-level="${level}"
                 draggable="${this.settings.enableDragDrop}"
                 onclick="this.closest('.advanced-tree-widget').component.selectNode(${node.id}, event.ctrlKey)"
                 oncontextmenu="this.closest('.advanced-tree-widget').component.showContextMenu(event, ${node.id})"
                 ondblclick="this.closest('.advanced-tree-widget').component._openNodeForm(${JSON.stringify(node).replace(/"/g, '&quot;')})">
                
                <div class="node-content" style="padding-left: ${level * 20}px">
                    <span class="node-toggle ${hasChildren ? 'has-children' : ''}"
                          onclick="event.stopPropagation(); this.closest('.advanced-tree-widget').component.toggleNode(${node.id})">
                        ${hasChildren ? (isExpanded ? '▼' : '▶') : ''}
                    </span>
                    
                    <span class="node-icon">${node.icon || '📂'}</span>
                    <span class="node-label">${node.name}</span>
                    <span class="node-meta">
                        ${node.budget_count > 0 ? `<span class="badge badge-info">${node.budget_count} 📊</span>` : ''}
                        ${node.child_count > 0 ? `<span class="badge badge-secondary">${node.child_count} 🏢</span>` : ''}
                    </span>
                </div>
                
                ${isExpanded && hasChildren ? 
                    node.children.map(child => this._renderNode(child, level + 1)).join('') : ''}
            </div>
        `;
    }

    _renderContextMenu() {
        if (!this.state.showContextMenu || !this.state.contextMenuNode) {
            return '';
        }

        const node = this.state.contextMenuNode;
        const pos = this.state.contextMenuPosition;

        return `
            <div class="context-menu" 
                 style="left: ${pos.x}px; top: ${pos.y}px; display: block;">
                <div class="context-menu-item" 
                     onclick="this.closest('.advanced-tree-widget').component.contextMenuAction('view')">
                    👁️ Переглянути
                </div>
                <div class="context-menu-item" 
                     onclick="this.closest('.advanced-tree-widget').component.contextMenuAction('edit')">
                    ✏️ Редагувати
                </div>
                <div class="context-menu-separator"></div>
                <div class="context-menu-item" 
                     onclick="this.closest('.advanced-tree-widget').component.contextMenuAction('create_child')">
                    ➕ Додати підрозділ
                </div>
                <div class="context-menu-item" 
                     onclick="this.closest('.advanced-tree-widget').component.contextMenuAction('create_budget')">
                    💰 Створити бюджет
                </div>
                ${node.budget_count > 0 ? `
                <div class="context-menu-item" 
                     onclick="this.closest('.advanced-tree-widget').component.contextMenuAction('view_budgets')">
                    📊 Переглянути бюджети
                </div>` : ''}
                <div class="context-menu-separator"></div>
                <div class="context-menu-item" 
                     onclick="this.closest('.advanced-tree-widget').component.contextMenuAction('clone')">
                    📋 Клонувати
                </div>
                <div class="context-menu-item" 
                     onclick="this.closest('.advanced-tree-widget').component.contextMenuAction('export')">
                    📤 Експорт
                </div>
                <div class="context-menu-separator"></div>
                <div class="context-menu-item danger" 
                     onclick="this.closest('.advanced-tree-widget').component.contextMenuAction('delete')">
                    🗑️ Видалити
                </div>
            </div>
        `;
    }

    _renderEmptyState() {
        return `
            <div class="tree-empty-state">
                <div class="empty-icon">🌳</div>
                <h3>Структура порожня</h3>
                <p>Додайте ЦБО для відображення дерева організації</p>
                <button class="btn btn-primary" 
                        onclick="this.closest('.advanced-tree-widget').component._createRootNode()">
                    ➕ Створити перше ЦБО
                </button>
            </div>
        `;
    }

    // Публічні методи для зовнішнього API
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
        this.state.treeData = this._processTreeData(this.state.treeData);
    }

    collapseAll() {
        this.state.expandedNodes.clear();
        this.state.treeData = this._processTreeData(this.state.treeData);
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
        this._performSearch();
    }
}

AdvancedTreeWidget.template = "budget.AdvancedTreeWidget";

// Реєстрація компонента
registry.category("fields").add("advanced_tree", AdvancedTreeWidget);

export default AdvancedTreeWidget;