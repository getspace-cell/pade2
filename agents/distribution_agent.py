import time
import json
import requests
from agents.base_agent import BaseAgent
from pade.behaviours.protocols import FipaRequestProtocol
from pade.acl.messages import ACLMessage


class DistributionAgent(BaseAgent):
    def __init__(self, aid, couriers_data, orders_data):
        super().__init__(aid)
        self.couriers_data = couriers_data
        self.orders_data = orders_data
        self.pending_orders = orders_data.copy()
        self.assigned_orders = []
        self.delivered_orders = []
        # Правильно инициализируем загрузку курьеров и отслеживание заказов
        self.courier_load = {str(courier['id']): 0.0 for courier in couriers_data}
        self.courier_orders = {str(courier['id']): [] for courier in couriers_data}  # Новый словарь для заказов
        self.next_courier_index = 0

        self.behaviours.append(DistributionInitBehaviour(self))

    def on_start(self):
        self.log("🎯 Агент распределения запущен")
        self.log(f"📦 Заказов: {len(self.orders_data)}, Курьеров: {len(self.couriers_data)}")

        # Инициализируем все заказы в GUI как ожидающие
        for order in self.orders_data:
            self.update_order_status(order['id'], "pending")

        # Обновляем статистику в GUI
        self.update_gui_statistics({
            "total_orders": len(self.orders_data),
            "pending_orders": len(self.pending_orders),
            "assigned_orders": len(self.assigned_orders),
            "delivered_orders": len(self.delivered_orders),
            "active_couriers": len(self.couriers_data),
            "total_capacity": sum(courier['max_capacity'] for courier in self.couriers_data),
            "used_capacity": sum(self.courier_load.values()),
            "system_load": 0.0
        })

        self.log("⏳ Ожидаем запуск всех курьеров...")
        time.sleep(5)
        behaviour = self.behaviours[0]
        behaviour.distribute_orders()

    def find_courier_for_order_round_robin(self, order):
        """Находим курьера по алгоритму Round Robin"""
        attempts = 0
        total_couriers = len(self.couriers_data)

        while attempts < total_couriers:
            courier = self.couriers_data[self.next_courier_index]

            # Проверяем, может ли курьер взять заказ
            courier_id = str(courier['id'])
            current_load = self.courier_load.get(courier_id, 0.0)
            available_capacity = courier['max_capacity'] - current_load

            if order["weight"] <= available_capacity:
                # Нашли подходящего курьера
                self.courier_load[courier_id] += order["weight"]
                self.courier_orders[courier_id].append(order['id'])  # Добавляем заказ курьеру

                # Переходим к следующему курьеру для следующего заказа
                self.next_courier_index = (self.next_courier_index + 1) % total_couriers

                self.log(f"🎯 Round Robin: заказ {order['id']} -> курьер {courier['name']} " +
                         f"(загрузка: {self.courier_load[courier_id]:.1f}/{courier['max_capacity']}кг)")
                return courier_id

            # Этот курьер не подходит, пробуем следующего
            self.next_courier_index = (self.next_courier_index + 1) % total_couriers
            attempts += 1

        # Ни один курьер не может взять заказ
        self.log(f"❌ Round Robin: ни один курьер не может взять заказ #{order['id']} ({order['weight']}кг)")
        return None

    def assign_order(self, order, courier_id):
        """Назначаем заказ курьеру"""
        courier_name = next((c['name'] for c in self.couriers_data if str(c['id']) == courier_id), "Неизвестный")

        # Обновляем статус заказа в GUI
        self.update_order_status(order['id'], "assigned", courier_name)

        self.send_message(f"courier_{courier_id}", {
            "type": "order_assignment",
            "order": order
        })

    def update_order_status(self, order_id, status, courier_name=None):
        """Обновляет статус заказа в GUI"""
        order_data = {
            "status": status,
            "assigned_courier": courier_name
        }

        try:
            requests.post(
                f"{self.gui_url}/api/update_order/{order_id}",
                json=order_data,
                timeout=1
            )
            self.log(f"🔄 Обновлен статус заказа #{order_id}: {status}")
        except Exception as e:
            self.log(f"⚠️ Не удалось обновить статус заказа #{order_id}: {e}")

    def update_gui_after_distribution(self):
        """Обновляем GUI после распределения"""
        total_capacity = sum(courier['max_capacity'] for courier in self.couriers_data)
        used_capacity = sum(self.courier_load.values())
        system_load = (used_capacity / total_capacity * 100) if total_capacity > 0 else 0

        self.update_gui_statistics({
            "pending_orders": len(self.pending_orders),
            "assigned_orders": len(self.assigned_orders),
            "used_capacity": used_capacity,
            "system_load": system_load
        })


class DistributionInitBehaviour(FipaRequestProtocol):
    def __init__(self, agent):
        super().__init__(agent, is_initiator=False)
        self.agent = agent

    def distribute_orders(self):
        """Распределяем заказы по алгоритму Round Robin"""
        if not self.agent.pending_orders:
            self.agent.log("✅ Все заказы распределены!")
            return

        self.agent.log("🚀 НАЧИНАЕМ РАСПРЕДЕЛЕНИЕ ЗАКАЗОВ ПО АЛГОРИТМУ ROUND ROBIN!")

        distributed_count = 0
        skipped_count = 0
        max_attempts = len(self.agent.pending_orders) * 2

        attempts = 0
        while self.agent.pending_orders and attempts < max_attempts:
            order = self.agent.pending_orders[0]
            self.agent.log(f"🔍 Round Robin: ищу курьера для заказа #{order['id']} ({order['weight']}кг)")

            courier_id = self.agent.find_courier_for_order_round_robin(order)

            if courier_id:
                self.agent.assign_order(order, courier_id)
                self.agent.pending_orders.remove(order)
                self.agent.assigned_orders.append(order)
                distributed_count += 1
                self.agent.log(f"✅ Заказ #{order['id']} назначен курьеру {courier_id}")
                skipped_count = 0

                # Обновляем GUI после каждого распределенного заказа
                self.agent.update_gui_after_distribution()

                # ОБНОВЛЯЕМ ДАННЫЕ КУРЬЕРА В GUI
                self.update_courier_gui(courier_id)
            else:
                skipped_count += 1
                self.agent.log(f"⏭️  Пропускаем заказ #{order['id']}, пробуем следующий...")
                self.agent.pending_orders.append(self.agent.pending_orders.pop(0))

                if skipped_count >= len(self.agent.pending_orders):
                    self.agent.log("⚠️  Не могу распределить оставшиеся заказы - недостаточно емкости курьеров")
                    break

            attempts += 1
            time.sleep(1)

        remaining_orders = len(self.agent.pending_orders)
        self.agent.log(f"📊 Распределение завершено! " +
                       f"Распределено: {distributed_count}, " +
                       f"Осталось: {remaining_orders}")

        # Выводим итоговую статистику
        self.agent.log("📈 ИТОГОВАЯ СТАТИСТИКА КУРЬЕРОВ:")
        for courier in self.agent.couriers_data:
            courier_id = str(courier['id'])
            load = self.agent.courier_load.get(courier_id, 0.0)
            orders_count = len(self.agent.courier_orders.get(courier_id, []))
            capacity = courier['max_capacity']
            utilization = (load / capacity) * 100 if capacity > 0 else 0
            self.agent.log(
                f"   🚗 {courier['name']}: {load:.1f}/{capacity:.1f}кг ({utilization:.1f}%), заказов: {orders_count}")

    def update_courier_gui(self, courier_id):
        """Обновляем данные курьера в GUI"""
        courier = next((c for c in self.agent.couriers_data if str(c['id']) == courier_id), None)
        if courier:
            current_load = self.agent.courier_load.get(courier_id, 0.0)
            assigned_orders = self.agent.courier_orders.get(courier_id, [])

            self.agent.update_gui_courier(courier_id, {
                "data": {
                    "id": courier['id'],
                    "name": courier['name'],
                    "transport_type": courier['transport_type'],
                    "max_capacity": courier['max_capacity']
                },
                "current_capacity": current_load,
                "assigned_orders": assigned_orders,
                "status": "delivering" if current_load > 0 else "available"
            })
            self.agent.log(
                f"🔄 Обновлен GUI курьера {courier['name']}: {current_load:.1f}кг, заказов: {len(assigned_orders)}")

    def handle_request(self, message):
        """Обрабатываем входящие запросы"""
        try:
            content = json.loads(message.content)
            msg_type = content.get("type")
            self.agent.log(f"📨 Получено сообщение: {msg_type} от {message.sender.name}")

            if msg_type == "order_accepted":
                self.handle_order_accepted(content)
            elif msg_type == "order_delivered":
                self.handle_order_delivered(content)

        except Exception as e:
            self.agent.log(f"❌ Ошибка обработки сообщения: {e}")

    def handle_order_accepted(self, content):
        courier_id = content["courier_id"]
        order_id = content["order_id"]
        courier_name = content["courier_name"]
        self.agent.log(f"👍 Курьер {courier_name} принял заказ #{order_id}")

    def handle_order_delivered(self, content):
        order_id = content["order_id"]
        courier_name = content["courier_name"]
        courier_id = content["courier_id"]

        self.agent.delivered_orders.append(order_id)

        # Уменьшаем загрузку курьера при доставке
        order_weight = next((order['weight'] for order in self.agent.orders_data if order['id'] == order_id), 0)
        if courier_id in self.agent.courier_load:
            self.agent.courier_load[courier_id] = max(0, self.agent.courier_load[courier_id] - order_weight)

        # Удаляем заказ из списка курьера
        if courier_id in self.agent.courier_orders and order_id in self.agent.courier_orders[courier_id]:
            self.agent.courier_orders[courier_id].remove(order_id)

        # Обновляем статус заказа на "доставлен"
        self.agent.update_order_status(order_id, "delivered", courier_name)

        self.agent.log(
            f"🎉 Заказ #{order_id} доставлен курьером {courier_name}! Всего доставлено: {len(self.agent.delivered_orders)}")

        # Обновляем GUI курьера после доставки
        self.update_courier_gui(courier_id)

        # Обновляем статистику в GUI
        self.agent.update_gui_statistics({
            "delivered_orders": len(self.agent.delivered_orders),
            "used_capacity": sum(self.agent.courier_load.values()),
            "pending_orders": len(self.agent.pending_orders),
            "assigned_orders": len(self.agent.assigned_orders) - len(self.agent.delivered_orders)
        })

        # Удаляем доставленный заказ из assigned_orders
        self.agent.assigned_orders = [order for order in self.agent.assigned_orders if order['id'] != order_id]

        # Если все заказы доставлены
        if len(self.agent.delivered_orders) == len(self.agent.orders_data):
            self.agent.log("🏁 ВСЕ ЗАКАЗЫ ДОСТАВЛЕНЫ! СИСТЕМА ЗАВЕРШИЛА РАБОТУ!")

            # Финальное обновление статистики
            self.agent.update_gui_statistics({
                "pending_orders": 0,
                "assigned_orders": 0,
                "delivered_orders": len(self.agent.delivered_orders),
                "used_capacity": 0.0,
                "system_load": 0.0
            })