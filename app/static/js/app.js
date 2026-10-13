function tableApp() {
    return {
        // App State
        status: {
            mode: 'loading',
            account_display: 'Checking...',
            connected: false,
            message: '',
            default_table: 'demotable'
        },
        tables: [],
        selectedTable: '',
        entities: [],
        dynamicColumns: [],
        selectedRows: [],
        isLoading: false,

        // Filters
        filters: {
            partitionKey: '',
            odataFilter: '',
            limit: 50
        },

        // Modals
        showEntityModal: false,
        entityModalMode: 'create', // 'create' | 'edit'
        entityInputTab: 'visual',  // 'visual' | 'json'
        activeEntity: { PartitionKey: '', RowKey: '' },
        activeEntityAttributes: [],
        rawEntityJson: '{}',

        showDetailModal: false,
        detailEntity: {},

        showNewTableModal: false,
        newTableName: '',

        showConfigModal: false,
        configInput: {
            connectionString: '',
            accountName: ''
        },

        // Toasts
        toasts: [],

        // Lifecycle
        async initApp() {
            await this.loadStatus();
            await this.loadTables();
            if (this.tables.length > 0) {
                // Pick default table if available, else first table
                if (this.tables.includes(this.status.default_table)) {
                    this.selectedTable = this.status.default_table;
                } else {
                    this.selectedTable = this.tables[0];
                }
                await this.loadEntities();
            } else {
                // If in in-memory mode or initial empty state, create default table
                this.selectedTable = this.status.default_table || 'demotable';
                await this.loadEntities();
            }
        },

        // API Calls
        async loadStatus() {
            try {
                const res = await fetch('/api/status');
                if (res.ok) {
                    this.status = await res.json();
                }
            } catch (e) {
                console.error('Failed to load status', e);
            }
        },

        async loadTables() {
            try {
                const res = await fetch('/api/tables');
                if (res.ok) {
                    const data = await res.json();
                    this.tables = data.tables || [];
                }
            } catch (e) {
                console.error('Failed to load tables', e);
            }
        },

        async loadEntities() {
            if (!this.selectedTable) return;
            this.isLoading = true;
            this.selectedRows = [];

            try {
                const params = new URLSearchParams();
                if (this.filters.partitionKey) params.append('partition_key', this.filters.partitionKey.trim());
                if (this.filters.odataFilter) params.append('filter_query', this.filters.odataFilter.trim());
                if (this.filters.limit) params.append('limit', this.filters.limit);

                const url = `/api/tables/${encodeURIComponent(this.selectedTable)}/entities?${params.toString()}`;
                const res = await fetch(url);
                
                if (res.ok) {
                    const data = await res.json();
                    this.entities = data.entities || [];
                    this.computeDynamicColumns();
                } else {
                    const err = await res.json();
                    this.showToast(err.detail || 'Failed to load entities', 'error');
                    this.entities = [];
                    this.dynamicColumns = [];
                }
            } catch (e) {
                this.showToast('Network error loading entities', 'error');
            } finally {
                this.isLoading = false;
                this.$nextTick(() => {
                    if (window.lucide) window.lucide.createIcons();
                });
            }
        },

        computeDynamicColumns() {
            const ignored = new Set(['PartitionKey', 'RowKey', 'Timestamp', 'odata.etag']);
            const colSet = new Set();
            for (const entity of this.entities) {
                for (const key of Object.keys(entity)) {
                    if (!ignored.has(key)) {
                        colSet.add(key);
                    }
                }
            }
            this.dynamicColumns = Array.from(colSet).sort();
        },

        resetFilters() {
            this.filters.partitionKey = '';
            this.filters.odataFilter = '';
            this.filters.limit = 50;
            this.loadEntities();
        },

        async createTable() {
            const name = this.newTableName.trim();
            if (!name) {
                this.showToast('Please enter a valid table name', 'warning');
                return;
            }

            try {
                const res = await fetch('/api/tables', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ name })
                });

                if (res.ok) {
                    this.showToast(`Table '${name}' created`, 'success');
                    this.showNewTableModal = false;
                    this.newTableName = '';
                    await this.loadTables();
                    this.selectedTable = name;
                    await this.loadEntities();
                } else {
                    const err = await res.json();
                    this.showToast(err.detail || 'Failed to create table', 'error');
                }
            } catch (e) {
                this.showToast('Network error creating table', 'error');
            }
        },

        async confirmDeleteTable() {
            if (!this.selectedTable) return;
            const confirmMsg = `Are you sure you want to delete table '${this.selectedTable}' and all its entities?`;
            if (!window.confirm(confirmMsg)) return;

            try {
                const res = await fetch(`/api/tables/${encodeURIComponent(this.selectedTable)}`, {
                    method: 'DELETE'
                });

                if (res.ok) {
                    this.showToast(`Table '${this.selectedTable}' deleted`, 'success');
                    await this.loadTables();
                    this.selectedTable = this.tables[0] || '';
                    await this.loadEntities();
                } else {
                    const err = await res.json();
                    this.showToast(err.detail || 'Failed to delete table', 'error');
                }
            } catch (e) {
                this.showToast('Network error deleting table', 'error');
            }
        },

        async seedData() {
            if (!this.selectedTable) {
                this.showToast('No table selected', 'warning');
                return;
            }

            this.isLoading = true;
            try {
                const res = await fetch(`/api/tables/${encodeURIComponent(this.selectedTable)}/seed`, {
                    method: 'POST'
                });

                if (res.ok) {
                    const data = await res.json();
                    this.showToast(data.message || 'Sample data seeded', 'success');
                    await this.loadEntities();
                } else {
                    const err = await res.json();
                    this.showToast(err.detail || 'Failed to seed sample data', 'error');
                }
            } catch (e) {
                this.showToast('Network error seeding data', 'error');
            } finally {
                this.isLoading = false;
            }
        },

        // Entity CRUD
        openEntityModal(mode, entity = null) {
            this.entityModalMode = mode;
            this.entityInputTab = 'visual';

            if (mode === 'create') {
                this.activeEntity = { PartitionKey: '', RowKey: '' };
                this.activeEntityAttributes = [
                    { key: 'Name', type: 'string', value: '' },
                    { key: 'Category', type: 'string', value: '' }
                ];
                this.rawEntityJson = JSON.stringify({
                    PartitionKey: '',
                    RowKey: '',
                    Name: '',
                    Category: ''
                }, null, 2);
            } else {
                // Edit mode
                this.activeEntity = {
                    PartitionKey: entity.PartitionKey,
                    RowKey: entity.RowKey
                };
                
                const attrs = [];
                const ignored = new Set(['PartitionKey', 'RowKey', 'Timestamp', 'odata.etag']);
                for (const [k, v] of Object.entries(entity)) {
                    if (!ignored.has(k)) {
                        let valType = 'string';
                        let valStr = String(v);
                        if (typeof v === 'number') {
                            valType = 'number';
                        } else if (typeof v === 'boolean') {
                            valType = 'boolean';
                            valStr = v ? 'true' : 'false';
                        }
                        attrs.push({ key: k, type: valType, value: valStr });
                    }
                }
                this.activeEntityAttributes = attrs;
                this.rawEntityJson = JSON.stringify(entity, null, 2);
            }

            this.showEntityModal = true;
            this.$nextTick(() => {
                if (window.lucide) window.lucide.createIcons();
            });
        },

        addEntityField() {
            this.activeEntityAttributes.push({ key: '', type: 'string', value: '' });
            this.$nextTick(() => {
                if (window.lucide) window.lucide.createIcons();
            });
        },

        removeEntityField(index) {
            this.activeEntityAttributes.splice(index, 1);
        },

        syncToRawJson() {
            const payload = {
                PartitionKey: this.activeEntity.PartitionKey,
                RowKey: this.activeEntity.RowKey
            };

            for (const attr of this.activeEntityAttributes) {
                if (attr.key && attr.key.trim()) {
                    const k = attr.key.trim();
                    let v = attr.value;
                    if (attr.type === 'number') {
                        v = Number(v) || 0;
                    } else if (attr.type === 'boolean') {
                        v = (v === 'true' || v === true);
                    }
                    payload[k] = v;
                }
            }

            this.rawEntityJson = JSON.stringify(payload, null, 2);
        },

        async saveEntity() {
            let payload = {};

            if (this.entityInputTab === 'json') {
                try {
                    payload = JSON.parse(this.rawEntityJson);
                } catch (e) {
                    this.showToast('Invalid JSON syntax', 'error');
                    return;
                }
            } else {
                if (!this.activeEntity.PartitionKey || !this.activeEntity.RowKey) {
                    this.showToast('PartitionKey and RowKey are required', 'warning');
                    return;
                }
                payload = {
                    PartitionKey: this.activeEntity.PartitionKey.trim(),
                    RowKey: this.activeEntity.RowKey.trim()
                };

                for (const attr of this.activeEntityAttributes) {
                    if (attr.key && attr.key.trim()) {
                        const k = attr.key.trim();
                        let v = attr.value;
                        if (attr.type === 'number') {
                            v = Number(v) || 0;
                        } else if (attr.type === 'boolean') {
                            v = (v === 'true' || v === true);
                        }
                        payload[k] = v;
                    }
                }
            }

            const pKey = encodeURIComponent(payload.PartitionKey);
            const rKey = encodeURIComponent(payload.RowKey);

            try {
                let res;
                if (this.entityModalMode === 'create') {
                    res = await fetch(`/api/tables/${encodeURIComponent(this.selectedTable)}/entities`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(payload)
                    });
                } else {
                    res = await fetch(`/api/tables/${encodeURIComponent(this.selectedTable)}/entities/${pKey}/${rKey}?mode=MERGE`, {
                        method: 'PUT',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(payload)
                    });
                }

                if (res.ok) {
                    this.showToast(`Entity [${payload.PartitionKey}, ${payload.RowKey}] saved`, 'success');
                    this.showEntityModal = false;
                    await this.loadEntities();
                } else {
                    const err = await res.json();
                    this.showToast(err.detail || 'Failed to save entity', 'error');
                }
            } catch (e) {
                this.showToast('Network error saving entity', 'error');
            }
        },

        viewEntity(entity) {
            this.detailEntity = entity;
            this.showDetailModal = true;
            this.$nextTick(() => {
                if (window.lucide) window.lucide.createIcons();
            });
        },

        async deleteSingleEntity(pKey, rKey) {
            if (!window.confirm(`Delete entity [${pKey}, ${rKey}]?`)) return;

            try {
                const res = await fetch(`/api/tables/${encodeURIComponent(this.selectedTable)}/entities/${encodeURIComponent(pKey)}/${encodeURIComponent(rKey)}`, {
                    method: 'DELETE'
                });

                if (res.ok) {
                    this.showToast(`Entity [${pKey}, ${rKey}] deleted`, 'success');
                    await this.loadEntities();
                } else {
                    const err = await res.json();
                    this.showToast(err.detail || 'Failed to delete entity', 'error');
                }
            } catch (e) {
                this.showToast('Network error deleting entity', 'error');
            }
        },

        // Selection & Batch Delete
        toggleSelectAll(e) {
            if (e.target.checked) {
                this.selectedRows = this.entities.map(ent => `${ent.PartitionKey}::${ent.RowKey}`);
            } else {
                this.selectedRows = [];
            }
        },

        isAllSelected() {
            return this.entities.length > 0 && this.selectedRows.length === this.entities.length;
        },

        async batchDeleteSelected() {
            if (this.selectedRows.length === 0) return;
            if (!window.confirm(`Delete ${this.selectedRows.length} selected entities?`)) return;

            const items = this.selectedRows.map(id => {
                const [PartitionKey, RowKey] = id.split('::');
                return { PartitionKey, RowKey };
            });

            try {
                const res = await fetch(`/api/tables/${encodeURIComponent(this.selectedTable)}/entities/batch-delete`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ items })
                });

                if (res.ok) {
                    const result = await res.json();
                    this.showToast(`Deleted ${result.deleted} entities`, 'success');
                    this.selectedRows = [];
                    await this.loadEntities();
                } else {
                    const err = await res.json();
                    this.showToast(err.detail || 'Failed batch delete', 'error');
                }
            } catch (e) {
                this.showToast('Network error executing batch delete', 'error');
            }
        },

        // Storage Config
        async applyConfig() {
            try {
                const res = await fetch('/api/configure', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        connection_string: this.configInput.connectionString || null,
                        account_name: this.configInput.accountName || null
                    })
                });

                if (res.ok) {
                    this.status = await res.json();
                    this.showToast('Configuration updated', 'success');
                    this.showConfigModal = false;
                    await this.loadTables();
                    await this.loadEntities();
                } else {
                    const err = await res.json();
                    this.showToast(err.detail || 'Failed to update configuration', 'error');
                }
            } catch (e) {
                this.showToast('Network error updating configuration', 'error');
            }
        },

        // Helpers
        formatValue(val) {
            if (val === null || val === undefined) return '-';
            if (typeof val === 'object') return JSON.stringify(val);
            return String(val);
        },

        showToast(message, type = 'info') {
            const id = Date.now() + Math.random();
            this.toasts.push({ id, message, type });
            setTimeout(() => {
                this.toasts = this.toasts.filter(t => t.id !== id);
            }, 3500);
        }
    };
}
