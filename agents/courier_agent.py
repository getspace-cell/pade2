import time
import json
from agents.base_agent import BaseAgent
from pade.behaviours.protocols import FipaRequestProtocol
import threading


class CourierAgent(BaseAgent):
    def __init__(self, aid, courier_data):
        super().__init__(aid)
        self.courier_data = courier_data
        self.current_orders = []
        self.current_capacity = 0.0
        self.status = "available"

        self.behaviours.append(CourierRequestBehaviour(self))

    def on_start(self):
        self.log(f"🚗 Курьер {self.courier_data['name']} запущен. Макс.груз: {self.courier_data['max_capacity']}кг")

        # ОБНОВЛЯЕМ GUI ПРИ СТАРТЕ
        self.update_gui()

    def update_gui(self):
        """Обновляем данные курьера в GUI"""
        courier_id = str(self.courier_data['id'])

        self.update_gui_courier(courier_id, {
            "data": {
                "id": self.courier_data['id'],
                "name": self.courier_data['name'],
                "transport_type": self.courier_data['transport_type'],
                "max_capacity": self.courier_data['max_capacity']
            },
            "current_capacity": self.current_capacity,
            "assigned_orders": [order['id'] for order in self.current_orders],
            "status": self.status
        })
        self.log(f"🔄 GUI обновлен для курьера {self.courier_data['name']}: {self.current_capacity}кг")


class CourierRequestBehaviour(FipaRequestProtocol):
    def __init__(self, agent):
        super().__init__(agent, is_initiator=False)
        self.agent = agent

    def handle_request(self, message):
        """Обрабатываем входящие запросы"""
        try:
            content = json.loads(message.content)
            msg_type = content.get("type")
            self.agent.log(f"📨 Получено сообщение: {msg_type}")

            if msg_type == "order_assignment":
                self.handle_order_assignment(content)

        except Exception as e:
            self.agent.log(f"❌ Ошибка обработки запроса: {e}")

    def handle_order_assignment(self, content):
        """Обрабатываем назначение заказа"""
        order_data = content["order"]
        self.agent.log(f"📨 Получен заказ #{order_data['id']} ({order_data['weight']}кг)")
        self.accept_order(order_data)

    def accept_order(self, order_data):
        """Принимаем заказ"""
        available_capacity = self.agent.courier_data["max_capacity"] - self.agent.current_capacity

        if available_capacity >= order_data["weight"]:
            self.agent.current_orders.append(order_data)
            self.agent.current_capacity += order_data["weight"]
            self.agent.status = "delivering"

            self.agent.log(
                f"✅ Принял заказ #{order_data['id']}. Загрузка: {self.agent.current_capacity}/{self.agent.courier_data['max_capacity']}кг")

            # ОБНОВЛЯЕМ GUI ПОСЛЕ ПРИНЯТИЯ ЗАКАЗА
            self.agent.update_gui()

            # Отправляем подтверждение
            self.agent.send_message("distribution_agent", {
                "type": "order_accepted",
                "courier_id": self.agent.courier_data["id"],
                "order_id": order_data["id"],
                "courier_name": self.agent.courier_data["name"]
            })

            # Имитируем доставку
            self.simulate_delivery(order_data)
        else:
            self.agent.log(f"❌ Не могу принять заказ #{order_data['id']} - превышена грузоподъемность")

    def simulate_delivery(self, order_data):
        """Имитируем доставку"""

        def deliver():
            # Имитируем время на доставку
            delivery_time = 2  # секунды
            self.agent.log(f"⏳ Доставляю заказ #{order_data['id']}... ({delivery_time}сек)")
            time.sleep(delivery_time)
            self.complete_delivery(order_data)

        delivery_thread = threading.Thread(target=deliver, daemon=True)
        delivery_thread.start()

    def complete_delivery(self, order_data):
        """Завершаем доставку"""
        order_id = order_data["id"]
        if order_data in self.agent.current_orders:
            self.agent.current_orders.remove(order_data)
            self.agent.current_capacity -= order_data["weight"]

        self.agent.log(f"📦 Доставил заказ #{order_id}. Осталось заказов: {len(self.agent.current_orders)}")

        # Уведомляем о доставке
        self.agent.send_message("distribution_agent", {
            "type": "order_delivered",
            "courier_id": self.agent.courier_data["id"],
            "order_id": order_id,
            "courier_name": self.agent.courier_data["name"]
        })

        if not self.agent.current_orders:
            self.agent.status = "available"
            self.agent.log("🟢 Снова доступен для заказов!")

        # ОБНОВЛЯЕМ GUI ПОСЛЕ ДОСТАВКИ
        self.agent.update_gui()