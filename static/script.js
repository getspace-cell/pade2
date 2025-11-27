class CourierSystemGUI {
    constructor() {
        this.ws = null;
        this.isConnected = false;
        this.state = {
            logs: [],
            statistics: {},
            couriers: {},
            orders: {}
        };

        this.init();
    }

    init() {
        this.connectWebSocket();
        this.setupEventListeners();
        this.setupFileUpload();
        console.log('🚀 CourierSystemGUI initialized');
    }

    connectWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws`;

        this.ws = new WebSocket(wsUrl);

        this.ws.onopen = () => {
            console.log('✅ WebSocket connected');
            this.isConnected = true;
            this.updateConnectionStatus('connected', '✅ Подключено');
        };

        this.ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                this.handleMessage(data);
            } catch (error) {
                console.error('❌ Error parsing message:', error);
            }
        };

        this.ws.onclose = () => {
            console.log('🔌 WebSocket disconnected');
            this.isConnected = false;
            this.updateConnectionStatus('disconnected', '🔌 Отключено');
            setTimeout(() => this.connectWebSocket(), 3000);
        };

        this.ws.onerror = (error) => {
            console.error('💥 WebSocket error:', error);
            this.updateConnectionStatus('error', '❌ Ошибка подключения');
        };
    }

    updateConnectionStatus(status, message) {
        const statusElement = document.getElementById('connectionStatus');
        statusElement.className = `status-${status}`;
        statusElement.textContent = message;
    }

    handleMessage(data) {
        console.log('📨 Received message type:', data.type);

        switch (data.type) {
            case 'initial_state':
                console.log('🎯 Initial state received');
                this.state = data.data;
                this.renderAll();
                break;
            case 'log_update':
                console.log('📝 Log update received');
                this.addLogEntry(data.log);
                this.updateDashboardOnNewLog();
                break;
            case 'courier_update':
                console.log('🚗 Courier update received for:', data.courier_id);
                this.updateCourierDisplay(data.courier_id, data.data);
                this.animateUpdate('activeCouriers');
                break;
            case 'order_update':
                console.log('📦 Order update received for:', data.order_id);
                this.updateOrderDisplay(data.order_id, data.data);
                break;
            case 'statistics_update':
                console.log('📊 Statistics update received');
                this.updateStatistics(data.statistics);
                this.animateStatisticsUpdate();
                break;
            case 'orders_list':
                console.log('📋 Orders list received');
                this.renderOrders(data.orders);
                break;
        }
    }

    renderAll() {
        this.renderStatistics();
        this.renderLogs();
        this.renderCouriers();
        this.renderOrders(this.state.orders);
    }

    renderStatistics() {
        const stats = this.state.statistics;

        document.getElementById('totalOrders').textContent = stats.total_orders || 0;
        document.getElementById('deliveredOrders').textContent = stats.delivered_orders || 0;
        document.getElementById('assignedOrders').textContent = stats.assigned_orders || 0;
        document.getElementById('systemLoad').textContent = `${(stats.system_load || 0).toFixed(1)}%`;

        const statsContainer = document.getElementById('statsContainer');
        if (Object.keys(stats).length === 0) {
            statsContainer.innerHTML = '<div class="no-data">Нет данных</div>';
            return;
        }

        const deliveryRate = stats.total_orders ? ((stats.delivered_orders / stats.total_orders) * 100) : 0;
        const capacityUsage = stats.total_capacity ? ((stats.used_capacity / stats.total_capacity) * 100) : 0;

        let html = `
            <div class="stat-item">
                <span>Всего курьеров:</span>
                <span>${stats.active_couriers || 0}</span>
            </div>
            <div class="stat-item">
                <span>Ожидающих заказов:</span>
                <span>${stats.pending_orders || 0}</span>
            </div>
            <div class="stat-item">
                <span>Общая грузоподъемность:</span>
                <span>${(stats.total_capacity || 0).toFixed(1)} кг</span>
            </div>
            <div class="stat-item">
                <span>Использовано:</span>
                <span>${(stats.used_capacity || 0).toFixed(1)} кг</span>
            </div>
            <div class="stat-item">
                <span>Процент доставки:</span>
                <span>${deliveryRate.toFixed(1)}%</span>
            </div>
            <div class="stat-item">
                <span>Использование емкости:</span>
                <span>${capacityUsage.toFixed(1)}%</span>
            </div>
        `;

        statsContainer.innerHTML = html;
    }

    addLogEntry(log) {
        const logsContainer = document.getElementById('logsContainer');

        if (logsContainer.querySelector('.no-data')) {
            logsContainer.innerHTML = '';
        }

        const time = new Date(log.timestamp * 1000).toLocaleTimeString();
        const logEntry = document.createElement('div');
        logEntry.className = 'log-entry';
        logEntry.innerHTML = `<span style="color: #666; font-size: 0.8em;">[${time}]</span> ${log.message}`;

        logsContainer.appendChild(logEntry);
        logsContainer.scrollTop = logsContainer.scrollHeight;
    }

    renderLogs() {
        const logsContainer = document.getElementById('logsContainer');
        const logs = this.state.logs || [];

        if (logs.length === 0) {
            logsContainer.innerHTML = '<div class="no-data">Нет сообщений</div>';
            return;
        }

        let html = '';
        logs.forEach(log => {
            const time = new Date(log.timestamp * 1000).toLocaleTimeString();
            html += `
                <div class="log-entry">
                    <span style="color: #666; font-size: 0.8em;">[${time}]</span>
                    ${log.message}
                </div>
            `;
        });

        logsContainer.innerHTML = html;
        logsContainer.scrollTop = logsContainer.scrollHeight;
    }

    renderCouriers() {
        const couriersContainer = document.getElementById('couriersContainer');
        const couriers = this.state.couriers || {};

        if (Object.keys(couriers).length === 0) {
            couriersContainer.innerHTML = '<div class="no-data">Нет данных о курьерах</div>';
            return;
        }

        let html = '';
        Object.values(couriers).forEach(courier => {
            html += this.createCourierCard(courier);
        });

        couriersContainer.innerHTML = html;
    }

    updateCourierDisplay(courierId, courierData) {
        const courierCard = document.querySelector(`[data-courier-id="${courierId}"]`);
        if (courierCard) {
            courierCard.outerHTML = this.createCourierCard(courierData);
        } else {
            this.renderCouriers();
        }
    }

    createCourierCard(courier) {
        const data = courier.data || {};
        const currentCapacity = courier.current_capacity || 0;
        const maxCapacity = data.max_capacity || 1;
        const loadPercent = maxCapacity ? (currentCapacity / maxCapacity) * 100 : 0;
        const statusClass = courier.status === 'delivering' ? 'delivering' : '';
        const statusText = courier.status === 'delivering' ? 'В доставке' : 'Доступен';
        const statusColor = courier.status === 'delivering' ? 'status-delivering' : 'status-available';
        const ordersCount = courier.assigned_orders ? courier.assigned_orders.length : 0;

        return `
            <div class="courier-card ${statusClass}" data-courier-id="${data.id}">
                <div class="courier-header">
                    <span class="courier-name">${data.name}</span>
                    <span class="courier-status ${statusColor}">${statusText}</span>
                </div>
                <div class="courier-details">
                    <div>
                        <span>Транспорт:</span>
                        <span>${this.getTransportIcon(data.transport_type)} ${data.transport_type}</span>
                    </div>
                    <div>
                        <span>Заказов:</span>
                        <span>${ordersCount}</span>
                    </div>
                    <div>
                        <span>Загрузка:</span>
                        <span>${currentCapacity.toFixed(1)}/${maxCapacity} кг</span>
                    </div>
                </div>
                <div class="progress-bar">
                    <div class="progress-fill" style="width: ${loadPercent}%"></div>
                </div>
                <div class="progress-text">${loadPercent.toFixed(1)}%</div>
            </div>
        `;
    }

    renderOrders(ordersData) {
        const ordersContainer = document.getElementById('ordersContainer');
        const orders = ordersData || {};

        if (Object.keys(orders).length === 0) {
            ordersContainer.innerHTML = '<div class="no-data">Нет данных о заказах</div>';
            return;
        }

        let html = '';
        Object.values(orders).forEach(order => {
            html += this.createOrderCard(order);
        });

        ordersContainer.innerHTML = html;
    }

    updateOrderDisplay(orderId, orderData) {
        const orderCard = document.querySelector(`[data-order-id="${orderId}"]`);
        if (orderCard) {
            orderCard.outerHTML = this.createOrderCard(orderData);
        } else {
            this.renderOrders(this.state.orders);
        }
    }

    createOrderCard(order) {
        const data = order.data || {};
        const status = order.status || 'pending';
        const statusText = this.getStatusText(status);
        const statusClass = `status-${status}`;
        const cardClass = `order-card ${status}`;

        return `
            <div class="${cardClass}" data-order-id="${data.id}">
                <div class="order-header">
                    <span class="order-id">📦 Заказ ${data.id}</span>
                    <span class="order-status ${statusClass}">${statusText}</span>
                </div>
                <div class="order-details">
                    <div class="order-weight">${data.weight} кг</div>
                    <div class="order-description">${data.description}</div>
                    <div class="order-recipient">
                        <span>${data.recipient || 'Получатель не указан'}</span>
                        <span>${data.assigned_courier ? `🚗 ${data.assigned_courier}` : ''}</span>
                    </div>
                </div>
            </div>
        `;
    }

    getStatusText(status) {
        const statusMap = {
            'pending': 'Ожидает',
            'assigned': 'Назначен',
            'delivered': 'Доставлен'
        };
        return statusMap[status] || status;
    }

    updateStatistics(newStats) {
        this.state.statistics = { ...this.state.statistics, ...newStats };
        this.renderStatistics();
    }

    updateDashboardOnNewLog() {
        this.renderStatistics();
    }

    animateStatisticsUpdate() {
        ['totalOrders', 'deliveredOrders', 'assignedOrders', 'systemLoad'].forEach(id => {
            this.animateUpdate(id);
        });
    }

    animateUpdate(elementId) {
        const element = document.getElementById(elementId);
        if (element) {
            element.style.transform = 'scale(1.1)';
            element.style.transition = 'transform 0.3s ease';
            setTimeout(() => {
                element.style.transform = 'scale(1)';
            }, 300);
        }
    }

    getTransportIcon(transportType) {
        const icons = {
            'car': '🚗',
            'bicycle': '🚲',
            'motorcycle': '🏍️',
            'foot': '🚶'
        };
        return icons[transportType] || '📦';
    }

    setupEventListeners() {
        setInterval(() => {
            if (this.isConnected) {
                this.ws.send(JSON.stringify({ type: 'ping' }));
            }
        }, 30000);
    }

    setupFileUpload() {
        const fileInput = document.getElementById('jsonFile');
        const statusDiv = document.getElementById('uploadStatus');

        fileInput.addEventListener('change', async (event) => {
            const file = event.target.files[0];
            if (!file) return;

            if (!file.name.endsWith('.json')) {
                statusDiv.innerHTML = '❌ Только JSON файлы разрешены';
                return;
            }

            const formData = new FormData();
            formData.append('file', file);

            try {
                statusDiv.innerHTML = '⏳ Загружаем файл...';

                const response = await fetch('/api/upload-json', {
                    method: 'POST',
                    body: formData
                });

                const result = await response.json();

                if (result.status === 'success') {
                    if (result.requires_restart) {
                        statusDiv.innerHTML = '🔄 Перезапускаем систему...';

                        const restartResponse = await fetch('/api/restart-system', {
                            method: 'POST'
                        });

                        const restartResult = await restartResponse.json();

                        if (restartResult.status === 'success') {
                            statusDiv.innerHTML = '✅ Система перезапускается...';
                            setTimeout(() => {
                                window.location.reload();
                            }, 4000);
                        } else {
                            statusDiv.innerHTML = '❌ Ошибка перезапуска';
                        }
                    } else {
                        statusDiv.innerHTML = `✅ ${result.message}`;
                        setTimeout(() => {
                            window.location.reload();
                        }, 2000);
                    }
                } else {
                    statusDiv.innerHTML = `❌ ${result.message}`;
                }
            } catch (error) {
                statusDiv.innerHTML = '❌ Ошибка загрузки файла';
                console.error('Upload error:', error);
            }

            fileInput.value = '';
        });
    }
}

document.addEventListener('DOMContentLoaded', () => {
    new CourierSystemGUI();
});