# [file name]: courier_agent.py
import time
import json
import random
import threading
from agents.base_agent import BaseAgent
from pade.pade.behaviours.protocols import FipaRequestProtocol


class CourierAgent(BaseAgent):
    def __init__(self, aid, courier_data):
        super().__init__(aid)
        self.courier_data = courier_data
        self.current_orders = []
        self.current_capacity = 0.0
        self.status = "available"
        self.communication_history = []
        self.known_couriers = []
        self.problems_encountered = 0
        self.helps_provided = 0
        self.location = "база"
        self.utilization = 0.0
        self.is_overloaded = False
        self.last_load_check = time.time()

        self.behaviours.append(CourierCommunicationBehaviour(self))

        # Запускаем периодическую активность
        self.start_periodic_activities()

    def start_periodic_activities(self):
        """Запускает периодические активности курьера"""

        def periodic_activity():
            while True:
                time.sleep(random.randint(30, 60))  # Увеличиваем интервал до 30-60 секунд
                self.check_own_load()
                # УБИРАЕМ случайные сообщения
                # self.random_communication()

        thread = threading.Thread(target=periodic_activity, daemon=True)
        thread.start()

    def on_start(self):
        self.log(f"🚗 Курьер {self.courier_data['name']} запущен. Макс.груз: {self.courier_data['max_capacity']}кг")
        self.introduce_to_others()
        self.update_gui()

    def check_own_load(self):
        """Проверяет собственную загрузку и инициирует перераспределение при необходимости"""
        self.calculate_utilization()

        # Если загрузка больше 90%, пытаемся отдать часть заказов
        if self.utilization > 90 and len(self.current_orders) > 1:
            self.log(f"⚠️  ПЕРЕГРУЗКА: {self.utilization:.1f}%! Пытаюсь отдать часть заказов")
            self.initiate_order_transfer()

    def calculate_utilization(self):
        """Рассчитывает процент загрузки"""
        capacity = self.courier_data['max_capacity']
        self.utilization = (self.current_capacity / capacity * 100) if capacity > 0 else 0
        self.is_overloaded = self.utilization > 80
        return self.utilization

    def initiate_order_transfer(self):
        """Инициирует передачу заказов другим курьерам"""
        if not self.current_orders:
            return

        # Сортируем заказы по весу (от самых тяжелых)
        sorted_orders = sorted(self.current_orders, key=lambda o: o['weight'], reverse=True)

        for order in sorted_orders:
            # Если заказ слишком тяжелый для нас, пытаемся передать
            if order['weight'] > self.courier_data['max_capacity'] * 0.3:
                self.log(f"🔄 Инициирую передачу заказа #{order['id']} ({order['weight']}кг)")

                # Уведомляем координатора о необходимости передачи
                self.send_message("coordinator_agent", {
                    "type": "transfer_initiated",
                    "from_courier_id": str(self.courier_data['id']),
                    "from_courier_name": self.courier_data['name'],
                    "order_id": order['id'],
                    "order_weight": order['weight'],
                    "reason": f"Перегрузка: {self.utilization:.1f}%",
                    "current_load": self.current_capacity,
                    "message": f"Прошу организовать передачу заказа #{order['id']}"
                })
                break

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
            "status": self.status,
            "message_count": len(self.communication_history),
            "location": self.location,
            "problems": self.problems_encountered,
            "helps": self.helps_provided,
            "utilization": self.utilization,
            "is_overloaded": self.is_overloaded
        })

    def ask_for_help(self, reason, order_id=None, severity="medium"):
        """Запрашивает помощь у других курьеров"""
        self.log(f"🆘 Запрашиваю помощь: {reason}")
        self.problems_encountered += 1

        self.send_message("coordinator_agent", {
            "type": "help_request",
            "courier_id": str(self.courier_data['id']),
            "reason": reason,
            "order_id": order_id,
            "severity": severity,
            "location": self.location,
            "current_load": self.current_capacity
        })

    def introduce_to_others(self):
        """Отправляет приветственные сообщения другим курьерам"""
        courier_id = str(self.courier_data['id'])

        # Отправляем координатору
        self.send_message("coordinator_agent", {
            "type": "courier_available",
            "courier_id": courier_id,
            "name": self.courier_data['name'],
            "transport_type": self.courier_data['transport_type'],
            "max_capacity": self.courier_data['max_capacity'],
            "message": f"Привет! Я {self.courier_data['name']}, готов к работе!"
        })

        self.log(f"👋 Я - {self.courier_data['name']}, готов к работе!")


class CourierCommunicationBehaviour(FipaRequestProtocol):
    def __init__(self, agent):
        super().__init__(agent, is_initiator=False)
        self.agent = agent

    def handle_request(self, message):
        """Обрабатываем входящие запросы"""
        try:
            content = json.loads(message.content)
            msg_type = content.get("type")
            self.agent.log(f"📨 Получено сообщение: {msg_type} от {message.sender.name}")

            # Логируем входящее сообщение в GUI
            self.agent.log_communication(message.sender.name, self.agent.agent_name,
                                         msg_type, content, "incoming")

            if msg_type == "order_assignment":
                self.handle_order_assignment(content, message.sender.name)
            elif msg_type == "transfer_proposal_incoming":
                self.handle_transfer_proposal(content)
            elif msg_type == "transfer_proposal_outgoing":
                self.handle_outgoing_transfer_proposal(content)
            elif msg_type == "load_info_response":
                self.handle_load_info_response(content)
            elif msg_type == "transfer_confirmed":
                self.handle_transfer_confirmed(content)
            elif msg_type == "help_assignment":
                self.handle_help_assignment(content)
            elif msg_type == "help_coordination":
                self.handle_help_coordination(content)
            elif msg_type == "joint_delivery_invitation":
                self.handle_joint_delivery_invitation(content)
            elif msg_type == "route_discussion":
                self.handle_route_discussion(content)
            elif msg_type == "system_broadcast":
                self.handle_system_broadcast(content)
            elif msg_type == "delivery_congratulations":
                self.handle_delivery_congratulations(content)
            elif msg_type == "welcome_message":
                self.handle_welcome_message(content)
            elif msg_type == "overload_info_response":
                self.handle_overload_info_response(content)
            elif msg_type == "no_overload_info":
                self.handle_no_overload_info(content)
            elif msg_type == "transfer_completed_incoming":
                self.handle_transfer_completed_incoming(content)
            elif msg_type == "transfer_completed_outgoing":
                self.handle_transfer_completed_outgoing(content)
            elif msg_type == "transfer_accepted":
                self.handle_transfer_accepted(content)
            elif msg_type == "transfer_declined":
                self.handle_transfer_declined(content)
            elif msg_type == "transfer_recommendation":
                self.handle_transfer_recommendation(content)
            elif msg_type == "transfer_opportunity":
                self.handle_transfer_opportunity(content)
            elif msg_type == "transfer_agreed":
                self.handle_transfer_agreed(content)

        except Exception as e:
            self.agent.log(f"❌ Ошибка обработки запроса: {e}")

    def handle_order_assignment(self, content, sender_name):
        """Обрабатывает назначение заказа"""
        order_data = content["order"]
        instruction = content.get("coordinator_instruction", "")
        details = content.get("details", {})

        self.agent.log(f"📨 Получен заказ #{order_data['id']} ({order_data['weight']}кг)")
        self.agent.log(f"📝 Инструкция от координатора: {instruction}")

        # Немедленно отвечаем координатору
        self.agent.send_message(sender_name, {
            "type": "order_accepted",
            "courier_id": self.agent.courier_data["id"],
            "order_id": order_data["id"],
            "courier_name": self.agent.courier_data["name"],
            "message": f"Заказ #{order_data['id']} принят. Начинаю выполнение!"
        })

        self.accept_order(order_data, details)

    def accept_order(self, order_data, details):
        """Принимаем заказ"""
        available_capacity = self.agent.courier_data["max_capacity"] - self.agent.current_capacity

        if available_capacity >= order_data["weight"]:
            self.agent.current_orders.append(order_data)
            self.agent.current_capacity += order_data["weight"]
            self.agent.calculate_utilization()
            self.agent.status = "delivering"
            self.agent.location = "отправляется на загрузку"

            self.agent.log(
                f"✅ Принял заказ #{order_data['id']}. Загрузка: {self.agent.current_capacity}/{self.agent.courier_data['max_capacity']}кг ({self.agent.utilization:.1f}%)")

            # ОБНОВЛЯЕМ GUI ПОСЛЕ ПРИНЯТИЯ ЗАКАЗА
            self.agent.update_gui()

            # Имитируем доставку
            self.simulate_delivery(order_data, details)
        else:
            self.agent.log(f"❌ Не могу принять заказ #{order_data['id']} - превышена грузоподъемность")

    def simulate_delivery(self, order_data, details):
        """Имитируем доставку с взаимодействием с другими курьерами"""

        def deliver():
            # Имитируем время на доставку
            base_time = random.randint(10, 20)  # секунды
            priority = details.get("priority", "normal")

            # Учитываем приоритет
            if priority == "urgent":
                delivery_time = base_time * 0.5
            elif priority == "high":
                delivery_time = base_time * 0.7
            else:
                delivery_time = base_time

            self.agent.log(f"⏳ Доставляю заказ #{order_data['id']}... ({int(delivery_time)}сек)")
            self.agent.location = f"в пути к {order_data.get('recipient', 'клиенту')}"
            self.agent.update_gui()

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
            self.agent.calculate_utilization()

        self.agent.log(f"📦 Доставил заказ #{order_id}. Осталось заказов: {len(self.agent.current_orders)}")
        self.agent.location = "возвращается на базу"

        # Уведомляем координатора о доставке
        self.agent.send_message("coordinator_agent", {
            "type": "order_delivered",
            "courier_id": self.agent.courier_data["id"],
            "order_id": order_id,
            "courier_name": self.agent.courier_data["name"],
            "message": f"Заказ #{order_id} успешно доставлен получателю {order_data.get('recipient', '')}",
            "delivery_time": time.strftime("%H:%M:%S")
        })

        if not self.agent.current_orders:
            self.agent.status = "available"
            self.agent.location = "база"
            self.agent.log("🟢 Снова доступен для заказов!")

        # ОБНОВЛЯЕМ GUI ПОСЛЕ ДОСТАВКИ
        self.agent.update_gui()

    def handle_transfer_proposal(self, content):
        """Обрабатывает предложение передачи заказа от координатора"""
        from_courier_id = content.get("from_courier_id")
        from_name = content.get("from_courier_name", "Коллега")
        order = content.get("order")
        reason = content.get("reason", "")
        conversation_id = content.get("conversation_id")

        # УДАЛЕНО: детальное логирование
        # self.agent.log(f"🔄 КУРЬЕР {from_name} предлагает передать мне заказ #{order['id']} ({order['weight']}кг)")
        # self.agent.log(f"📋 Причина: {reason}")

        # Простое логирование
        self.agent.log(f"🔄 Получил предложение передачи заказа #{order['id']} от {from_name}")

        # Проверяем, можем ли мы принять заказ
        available_capacity = self.agent.courier_data['max_capacity'] - self.agent.current_capacity

        if order['weight'] <= available_capacity:
            # Принимаем заказ
            self.agent.log(f"✅ Принял заказ #{order['id']} от {from_name}")

            # Сообщаем координатору о согласии
            self.agent.send_message("coordinator_agent", {
                "type": "transfer_agreement",
                "from_courier_id": from_courier_id,
                "to_courier_id": str(self.agent.courier_data['id']),
                "order_id": order['id'],
                "conversation_id": conversation_id,
                "message": f"Принял заказ #{order['id']} от {from_name}",
                "from_courier_name": from_name,
                "to_courier_name": self.agent.courier_data['name']
            })
        else:
            # Отказываемся
            self.agent.log(f"❌ Не могу принять заказ #{order['id']} от {from_name}")

            self.agent.send_message("coordinator_agent", {
                "type": "transfer_declined",
                "from_courier_id": from_courier_id,
                "to_courier_id": str(self.agent.courier_data['id']),
                "order_id": order['id'],
                "reason": f"Недостаточно места. Свободно: {available_capacity:.1f}кг, требуется: {order['weight']}кг",
                "from_courier_name": from_name,
                "to_courier_name": self.agent.courier_data['name']
            })

    def handle_outgoing_transfer_proposal(self, content):
        """Обрабатывает исходящее предложение передачи (от нас другому)"""
        order = content.get("order")
        to_courier_id = content.get("to_courier_id")
        to_courier_name = content.get("to_courier_name")
        reason = content.get("reason", "")

        # ИЗМЕНЕНИЕ: Более информативное сообщение
        self.agent.log(f"🔄 Я предложил передать заказ #{order['id']} курьеру {to_courier_name}")
        self.agent.log(f"📋 Причина: {reason}")

    def handle_load_info_response(self, content):
        """Обрабатывает информацию о загрузке от координатора"""
        system_load = content.get("system_load", 0)
        courier_loads = content.get("courier_loads", {})
        target_load = content.get("target_load", 80)

        self.agent.log(f"📊 Информация о загрузке: система {system_load:.1f}%, цель {target_load}%")

    def handle_transfer_confirmed(self, content):
        """Обрабатывает подтверждение передачи от координатора"""
        order_id = content.get("order_id")
        to_courier_id = content.get("to_courier_id")

        # Удаляем заказ из нашего списка
        order_to_remove = next((o for o in self.agent.current_orders if o['id'] == order_id), None)
        if order_to_remove:
            self.agent.current_orders.remove(order_to_remove)
            self.agent.current_capacity -= order_to_remove['weight']
            self.agent.calculate_utilization()

            self.agent.log(f"✅ Координатор подтвердил передачу заказа #{order_id}")
            self.agent.log(f"   📊 Новая загрузка: {self.agent.utilization:.1f}%")

            # Обновляем GUI
            self.agent.update_gui()

    def handle_overload_info_response(self, content):
        """Обрабатывает информацию о перегруженных курьерах"""
        most_overloaded = content.get("most_overloaded", {})
        available_overloaded = content.get("available_overloaded", [])

        if most_overloaded:
            self.agent.log(
                f"🤝 Самый перегруженный коллега: {most_overloaded['name']} ({most_overloaded['utilization']:.1f}%)")

    def handle_no_overload_info(self, content):
        """Обрабатывает отсутствие информации о перегруженных"""
        self.agent.log("ℹ️  В системе нет перегруженных курьеров в данный момент")

    def handle_transfer_completed_incoming(self, content):
        """Обрабатывает завершение входящей передачи"""
        order_id = content.get("order_id")
        from_courier_name = content.get("from_courier_name")

        self.agent.log(f"✅ Получил заказ #{order_id} от курьера {from_courier_name}")

        # Обновляем GUI
        self.agent.update_gui()

    def handle_transfer_completed_outgoing(self, content):
        """Обрабатывает завершение исходящей передачи"""
        order_id = content.get("order_id")
        to_courier_name = content.get("to_courier_name")

        self.agent.log(f"✅ Передача заказа #{order_id} курьеру {to_courier_name} завершена")

    def handle_transfer_accepted(self, content):
        """Обрабатывает принятие передачи"""
        to_courier_id = content.get("to_courier_id")
        to_name = content.get("to_name")
        order_id = content.get("order_id")

        self.agent.log(f"🤝 {to_name} принял предложение о передаче заказа #{order_id}")

    def handle_transfer_declined(self, content):
        """Обрабатывает отклонение передачи"""
        to_courier_id = content.get("to_courier_id")
        reason = content.get("reason", "")

        self.agent.log(f"❌ Курьер {to_courier_id} отклонил передачу: {reason}")

    def handle_transfer_recommendation(self, content):
        """Обрабатывает рекомендацию о передаче заказа"""
        order_id = content.get("order_id")
        to_courier_name = content.get("to_courier_name")
        reason = content.get("reason", "")

        self.agent.log(f"💡 Координатор рекомендует передать заказ #{order_id} курьеру {to_courier_name}")
        self.agent.log(f"📋 Причина: {reason}")

    def handle_transfer_opportunity(self, content):
        """Обрабатывает возможность принять заказ"""
        order_id = content.get("order_id")
        from_courier_name = content.get("from_courier_name")
        reason = content.get("reason", "")

        self.agent.log(f"💡 Координатор предлагает принять заказ #{order_id} от {from_courier_name}")
        self.agent.log(f"📋 Причина: {reason}")

    def handle_transfer_agreed(self, content):
        """Обрабатывает подтверждение передачи"""
        order_id = content.get("order_id")
        to_courier_name = content.get("to_courier_name")

        self.agent.log(f"✅ Передача заказа #{order_id} курьеру {to_courier_name} согласована")

    def handle_help_assignment(self, content):
        """Обрабатывает назначение помощи от координатора"""
        helping_courier_id = content["helping_courier_id"]
        reason = content.get("reason", "")
        order_id = content.get("order_id")
        conversation_id = content.get("conversation_id")

        self.agent.log(f"🎯 Координатор просит помочь курьеру {helping_courier_id}. Причина: {reason}")
        self.agent.helps_provided += 1

        # Сообщаем координатору о принятии задания
        self.agent.send_message("coordinator_agent", {
            "type": "help_assignment_accepted",
            "courier_id": str(self.agent.courier_data['id']),
            "helping_courier_id": helping_courier_id,
            "conversation_id": conversation_id,
            "message": "Принял задание по оказанию помощи."
        })

    def handle_help_coordination(self, content):
        """Обрабатывает координацию помощи"""
        helper_id = content.get("helper_id")
        helper_name = content.get("helper_name")
        conversation_id = content.get("conversation_id")
        message = content.get("message", "")

        self.agent.log(f"🤝 Координация помощи с {helper_name}")
        self.agent.log(f"💬 {message}")

    def handle_joint_delivery_invitation(self, content):
        """Обрабатывает приглашение к совместной доставке"""
        order_id = content.get("order_id")
        order_weight = content.get("order_weight")
        order_description = content.get("order_description")
        conversation_id = content.get("conversation_id")
        required_capacity = content.get("required_capacity")

        self.agent.log(f"🤝 Приглашение на совместную доставку заказа #{order_id} ({order_weight}кг)")

    def handle_route_discussion(self, content):
        """Обрабатывает обсуждение маршрута"""
        order_id = content.get("order_id")
        partner_id = content.get("partner_id")
        message = content.get("message", "")

        self.agent.log(f"🗺️ Обсуждение маршрута для заказа #{order_id} с курьером {partner_id}")

    def handle_system_broadcast(self, content):
        """Обрабатывает системную рассылку"""
        pending_orders = content.get("pending_orders", 0)
        delivered_orders = content.get("delivered_orders", 0)
        system_load = content.get("system_load", 0)

        self.agent.log(f"📢 Системная информация: Ожидает {pending_orders} заказов, "
                       f"Доставлено {delivered_orders}, Загрузка системы: {system_load:.1f}%")

    def handle_delivery_congratulations(self, content):
        """Обрабатывает поздравление с доставкой"""
        order_id = content.get("order_id")
        message = content.get("message", "")

        self.agent.log(f"🎉 {message}")

    def handle_welcome_message(self, content):
        """Обрабатывает приветственное сообщение"""
        message = content.get("message", "")
        system_status = content.get("system_status", {})

        self.agent.log(f"👋 {message}")
        self.agent.log(f"📊 Статус системы: {system_status.get('pending_orders', 0)} ожидающих заказов")