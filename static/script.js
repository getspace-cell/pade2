// [file name]: app.js
class CourierSystemGUI {
    constructor() {
        this.ws = null;
        this.isConnected = false;
        this.state = {
            logs: [],
            statistics: {},
            couriers: {},
            orders: {},
            communications: []
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
            case 'communication_update':
                console.log('💬 Communication update received');
                this.addCommunication(data.communication);
                if (data.total_messages !== undefined) {
                    this.updateMessagesCount(data.total_messages);
                }
                break;
            case 'communications_list':
                console.log('📋 Communications list received');
                this.renderCommunications(data.communications || []);
                break;
            case 'balance_report':
                console.log('⚖️ Balance report received');
                this.updateBalanceDisplay(data);
                break;
            case 'transfer_notification':
                console.log('🔄 Transfer notification received');
                this.showTransferNotification(data);
                break;
        }
    }

    updateMessagesCount(count) {
        const messagesElement = document.getElementById('messagesCount');
        if (messagesElement) {
            messagesElement.textContent = count;
            this.animateUpdate('messagesCount');
        }
    }

    updateBalanceDisplay(balanceData) {
        // Обновляем статистику системы
        const systemLoad = balanceData.system_load || 0;
        document.getElementById('systemLoad').textContent = `${systemLoad.toFixed(1)}%`;
    }

    showTransferNotification(transferData) {
        const fromName = transferData.from_name || 'Коллега';
        const toName = transferData.to_name || 'Коллега';
        const orderId = transferData.order_id || 'N/A';

        this.addToast(`🔄 ${fromName} → ${toName}: передача заказа #${orderId}`, 'info');
    }

    addToast(message, type = 'info') {
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.innerHTML = `
            <div class="toast-content">
                <span>${message}</span>
                <button class="toast-close" onclick="this.parentElement.parentElement.remove()">×</button>
            </div>
        `;

        document.body.appendChild(toast);

        // Удаляем через 5 секунд
        setTimeout(() => {
            if (toast.parentElement) {
                toast.remove();
            }
        }, 5000);
    }

    renderAll() {
        this.renderStatistics();
        this.renderLogs();
        this.renderCouriers();
        this.renderOrders(this.state.orders);
        this.renderCommunications(this.state.communications || []);

        this.updateMessagesCount(this.state.statistics.messages_exchanged || 0);
    }

    renderStatistics() {
        const stats = this.state.statistics;

        document.getElementById('totalOrders').textContent = stats.total_orders || 0;
        document.getElementById('deliveredOrders').textContent = stats.delivered_orders || 0;
        this.updateMessagesCount(stats.messages_exchanged || 0);

        // ФИКС: Убираем "цель" из загрузки системы
        const systemLoad = stats.system_load || 0;
        document.getElementById('systemLoad').textContent = `${systemLoad.toFixed(1)}%`;

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
                <span>Назначенных заказов:</span>
                <span>${stats.assigned_orders || 0}</span>
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
            <div class="stat-item">
                <span>Сообщений:</span>
                <span>${stats.messages_exchanged || 0}</span>
            </div>
        `;

        // Добавляем информацию о балансировке, если есть
        if (stats.load_imbalance !== undefined) {
            html += `
                <div class="stat-item">
                    <span>Дисбаланс:</span>
                    <span>${stats.load_imbalance.toFixed(1)}%</span>
                </div>
                <div class="stat-item">
                    <span>Передач заказов:</span>
                    <span>${stats.transfers_completed || 0}</span>
                </div>
            `;
        }

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
        const messageCount = courier.message_count || 0;
        const utilization = courier.utilization || loadPercent;

        // Определяем перегрузку
        let balanceClass = '';
        let balanceInfo = '';

        if (utilization > 80) {
            balanceClass = 'overloaded';
            balanceInfo = `<div class="overload-warning">ПЕРЕГРУЗКА! ${utilization.toFixed(1)}%</div>`;
        } else if (utilization < 30) {
            balanceClass = 'underloaded';
            balanceInfo = `<div class="underload-info">НЕДОГРУЗКА ${utilization.toFixed(1)}%</div>`;
        }

        return `
            <div class="courier-card ${statusClass} ${balanceClass}" data-courier-id="${data.id}">
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
                    <div>
                        <span>Утилизация:</span>
                        <span>${utilization.toFixed(1)}%</span>
                    </div>
                    <div>
                        <span>Сообщений:</span>
                        <span>${messageCount}</span>
                    </div>
                </div>
                <div class="progress-bar">
                    <div class="progress-fill" style="width: ${loadPercent}%"></div>
                </div>
                <div class="progress-text">${loadPercent.toFixed(1)}%</div>
                ${balanceInfo}
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

    renderCommunications(communications) {
        const container = document.getElementById('communicationsContainer');

        if (!communications || communications.length === 0) {
            container.innerHTML = '<div class="no-data">Нет сообщений</div>';
            return;
        }

        let html = '';
        communications.forEach(msg => {
            html += this.createMessageCard(msg);
        });

        container.innerHTML = html || '<div class="no-data">Нет сообщений</div>';

        if (html) {
            container.scrollTop = container.scrollHeight;
        }
    }

    addCommunication(communication) {
        const container = document.getElementById('communicationsContainer');

        if (container.querySelector('.no-data')) {
            container.innerHTML = '';
        }

        const messageCard = this.createMessageCard(communication);
        container.innerHTML += messageCard;
        container.scrollTop = container.scrollHeight;
    }

    createMessageCard(message) {
        const direction = message.direction || 'unknown';
        const directionClass = direction === 'incoming' ? 'direction-incoming' : 'direction-outgoing';
        const directionIcon = direction === 'incoming' ? '📥' : '📤';
        const directionText = direction === 'incoming' ? 'Входящее' : 'Исходящее';

        const type = message.type || 'unknown';
        const typeClass = this.getMessageTypeClass(type);

        let contentHtml = '';
        if (typeof message.content === 'object') {
            contentHtml = Object.entries(message.content)
                .map(([key, value]) => {
                    if (typeof value === 'object' && value !== null) {
                        return `<div><strong>${key}:</strong> ${JSON.stringify(value, null, 2)}</div>`;
                    }
                    return `<div><strong>${key}:</strong> ${value}</div>`;
                })
                .join('');
        } else {
            contentHtml = `<div>${message.content}</div>`;
        }

        return `
            <div class="message-card ${direction} ${typeClass}" data-message-id="${message.id}">
                <div class="message-header">
                    <div class="message-direction ${directionClass}">
                        ${directionIcon} ${directionText}
                    </div>
                    <div class="message-time">${message.time_str || ''}</div>
                </div>
                <div class="message-participants">
                    ${message.sender} → ${message.receiver}
                </div>
                <div class="message-type">${type}</div>
                <div class="message-content">
                    ${contentHtml}
                </div>
            </div>
        `;
    }

    getMessageTypeClass(type) {
        if (type.includes('help')) return 'help';
        if (type.includes('order') || type.includes('assignment') || type.includes('delivery')) return 'coordination';
        if (type.includes('transfer')) return 'transfer';
        return '';
    }

    updateStatistics(newStats) {
        this.state.statistics = { ...this.state.statistics, ...newStats };
        this.renderStatistics();
    }

    updateDashboardOnNewLog() {
        this.renderStatistics();
    }

    animateStatisticsUpdate() {
        ['totalOrders', 'deliveredOrders', 'systemLoad', 'messagesCount'].forEach(id => {
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

    getStatusText(status) {
        const statusMap = {
            'pending': 'Ожидает',
            'assigned': 'Назначен',
            'delivering': 'В доставке',
            'delivered': 'Доставлен'
        };
        return statusMap[status] || status;
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

// Добавляем стили для тостов и балансировки
const additionalStyles = `
    <style>
        .toast {
            position: fixed;
            top: 20px;
            right: 20px;
            background: white;
            border-radius: 8px;
            padding: 12px 16px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            z-index: 1000;
            animation: slideIn 0.3s ease;
            border-left: 4px solid #3498db;
            max-width: 300px;
        }

        .toast.info {
            border-left-color: #3498db;
            background: #e3f2fd;
        }

        .toast.warning {
            border-left-color: #e74c3c;
            background: #ffeaea;
        }

        .toast.success {
            border-left-color: #2ecc71;
            background: #e8f5e8;
        }

        .toast-content {
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .toast-close {
            background: none;
            border: none;
            font-size: 20px;
            cursor: pointer;
            color: #666;
            margin-left: 10px;
        }

        @keyframes slideIn {
            from {
                transform: translateX(100%);
                opacity: 0;
            }
            to {
                transform: translateX(0);
                opacity: 1;
            }
        }

        .message-card.transfer .message-type {
            background: #9b59b6;
            color: white;
        }

        .courier-card.overloaded {
            border-left-color: #e74c3c;
            background: linear-gradient(135deg, #ffeaea, #ffdbdb);
        }

        .courier-card.underloaded {
            border-left-color: #3498db;
            background: linear-gradient(135deg, #e3f2fd, #bbdefb);
        }

        .overload-warning {
            background: #e74c3c;
            color: white;
            padding: 6px 12px;
            border-radius: 8px;
            font-size: 0.85em;
            margin-top: 10px;
            text-align: center;
            font-weight: bold;
            animation: fadeIn 0.5s ease;
        }

        .underload-info {
            background: #3498db;
            color: white;
            padding: 6px 12px;
            border-radius: 8px;
            font-size: 0.85em;
            margin-top: 10px;
            text-align: center;
            font-weight: bold;
            animation: fadeIn 0.5s ease;
        }

        @keyframes fadeIn {
            from { opacity: 0; }
            to { opacity: 1; }
        }
    </style>
`;

document.addEventListener('DOMContentLoaded', () => {
    document.head.insertAdjacentHTML('beforeend', additionalStyles);
    new CourierSystemGUI();
});