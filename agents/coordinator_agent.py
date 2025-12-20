# [file name]: coordinator_agent.py
import json
import time
import random
import threading
from agents.base_agent import BaseAgent
from pade.pade.behaviours.protocols import FipaRequestProtocol
from pade.pade.acl.messages import ACLMessage


class CoordinatorAgent(BaseAgent):
    def __init__(self, aid, couriers_data, orders_data):
        super().__init__(aid)
        self.couriers_data = couriers_data
        self.orders_data = orders_data
        self.pending_orders = orders_data.copy()
        self.assigned_orders = []
        self.delivered_orders = []

        # Инициализируем курьеров
        self.courier_status = {}
        self.courier_load = {}
        self.courier_orders = {}
        self.courier_locations = {}

        for courier in couriers_data:
            courier_id = str(courier['id'])
            self.courier_status[courier_id] = "available"
            self.courier_load[courier_id] = 0.0
            self.courier_orders[courier_id] = []
            self.courier_locations[courier_id] = "база"

        self.behaviours.append(CoordinatorBehaviour(self))
        self.communication_history = []
        self.active_conversations = {}

        # Запускаем периодическую активность
        self.start_periodic_activities()

    def start_periodic_activities(self):
        """Запускает периодические активности координатора"""

        def periodic_check():
            while True:
                time.sleep(10)  # Каждые 10 секунд
                self.check_system_status()
                self.broadcast_system_info()

        thread = threading.Thread(target=periodic_check, daemon=True)
        thread.start()

    def on_start(self):
        self.log("🎯 Агент координации запущен")
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
            "used_capacity": 0.0,
            "system_load": 0.0,
            "messages_exchanged": 0
        })

        self.log("⏳ Ожидаем запуск всех курьеров...")
        time.sleep(3)
        behaviour = self.behaviours[0]
        behaviour.start_coordination()

    def log_communication(self, sender, receiver, msg_type, content):
        """Переопределяем для обновления статистики сообщений"""
        # Сохраняем сообщение в историю
        message = {
            "sender": sender,
            "receiver": receiver,
            "type": msg_type,
            "content": content,
            "timestamp": time.time(),
            "direction": "outgoing" if sender == self.agent_name else "incoming"
        }
        self.communication_history.append(message)

        # Вызываем родительский метод
        super().log_communication(sender, receiver, msg_type, content)

        # Обновляем статистику сообщений
        self.update_gui_statistics({
            "messages_exchanged": len(self.communication_history)
        })

    def find_best_courier_for_order(self, order):
        """Находит лучшего курьера для заказа на основе нескольких факторов"""
        suitable_couriers = []

        for courier in self.couriers_data:
            courier_id = str(courier['id'])
            current_load = self.courier_load.get(courier_id, 0.0)
            available_capacity = courier['max_capacity'] - current_load

            if order["weight"] <= available_capacity:
                # Рассчитываем приоритет курьера
                priority_score = self.calculate_courier_priority(courier, order, current_load)
                suitable_couriers.append({
                    "courier": courier,
                    "courier_id": courier_id,
                    "priority_score": priority_score,
                    "current_load": current_load
                })

        if not suitable_couriers:
            self.log(f"❌ Нет подходящих курьеров для заказа #{order['id']} ({order['weight']}кг)")

            # Пытаемся организовать совместную доставку
            self.organize_joint_delivery(order)
            return None

        # Выбираем курьера с наивысшим приоритетом
        best_courier = max(suitable_couriers, key=lambda x: x["priority_score"])

        # Обновляем нагрузку курьера
        self.courier_load[best_courier["courier_id"]] += order["weight"]
        self.courier_orders[best_courier["courier_id"]].append(order['id'])

        self.log(f"🎯 Координатор: заказ {order['id']} → курьер {best_courier['courier']['name']} "
                 f"(приоритет: {best_courier['priority_score']:.2f}, "
                 f"загрузка: {self.courier_load[best_courier['courier_id']]:.1f}/{best_courier['courier']['max_capacity']}кг)")

        # Отправляем уведомление о загрузке
        self.notify_couriers_about_load()

        return best_courier["courier_id"]

    def calculate_courier_priority(self, courier, order, current_load):
        """Рассчитывает приоритет курьера для конкретного заказа"""
        score = 0.0

        # Фактор 1: Свободная емкость (чем больше свободно, тем выше приоритет)
        free_capacity = courier['max_capacity'] - current_load
        score += (free_capacity / courier['max_capacity']) * 40

        # Фактор 2: Совместимость транспорта
        transport_bonus = {
            "car": 30,
            "motorcycle": 25,
            "bicycle": 20,
            "foot": 15
        }.get(courier['transport_type'], 10)
        score += transport_bonus

        # Фактор 3: Приоритет заказа
        priority_bonus = {
            "urgent": 25,
            "high": 15,
            "normal": 5
        }.get(order.get("priority", "normal"), 0)
        score += priority_bonus

        # Фактор 4: Загрузка курьера
        utilization = current_load / courier['max_capacity'] if courier['max_capacity'] > 0 else 0
        score += (1 - utilization) * 20

        # Фактор 5: Случайный фактор для разнообразия
        score += random.uniform(0, 10)

        return score

    def organize_joint_delivery(self, order):
        """Организует совместную доставку тяжелых заказов"""
        self.log(f"🔄 Координатор: пытаюсь организовать совместную доставку заказа #{order['id']} ({order['weight']}кг)")

        # Создаем тему для обсуждения
        conversation_id = f"joint_delivery_{order['id']}"
        self.active_conversations[conversation_id] = {
            "order": order,
            "participants": [],
            "status": "searching",
            "start_time": time.time()
        }

        # Рассылаем запрос всем курьерам
        for courier in self.couriers_data:
            courier_id = str(courier['id'])
            free_capacity = courier['max_capacity'] - self.courier_load.get(courier_id, 0.0)

            if free_capacity > order["weight"] * 0.3:  # Может взять хотя бы часть
                self.send_message(f"courier_{courier_id}", {
                    "type": "joint_delivery_invitation",
                    "order_id": order['id'],
                    "order_weight": order["weight"],
                    "order_description": order["description"],
                    "conversation_id": conversation_id,
                    "required_capacity": order["weight"] / 2  # Примерно половина
                })

        self.log(f"📢 Координатор: разослал приглашения на совместную доставку заказа #{order['id']}")

    def send_coordination_message(self, courier1_id, courier2_id, order, delivery_type):
        """Отправляет сообщение координации между курьерами"""
        message_content = {
            "type": "coordination_request",
            "delivery_type": delivery_type,
            "order_id": order["id"],
            "order_weight": order["weight"],
            "partner_courier_id": courier2_id if delivery_type == "joint_delivery" else None,
            "instruction": f"Обсудите совместную доставку заказа #{order['id']}"
        }

        self.send_message(f"courier_{courier1_id}", message_content)

    def update_gui_after_distribution(self):
        """Обновляем GUI после распределения"""
        total_capacity = sum(courier['max_capacity'] for courier in self.couriers_data)
        used_capacity = sum(self.courier_load.values())
        system_load = (used_capacity / total_capacity * 100) if total_capacity > 0 else 0

        self.update_gui_statistics({
            "pending_orders": len(self.pending_orders),
            "assigned_orders": len(self.assigned_orders),
            "used_capacity": used_capacity,
            "system_load": system_load,
            "messages_exchanged": len(self.communication_history)
        })

    def calculate_system_load(self):
        """Рассчитывает загрузку системы"""
        total_capacity = sum(courier['max_capacity'] for courier in self.couriers_data)
        used_capacity = sum(self.courier_load.values())
        return (used_capacity / total_capacity * 100) if total_capacity > 0 else 0

    def check_system_status(self):
        """Периодическая проверка статуса системы"""
        pending = len(self.pending_orders)
        delivering = sum(1 for status in self.courier_status.values()
                         if status == "delivering")

        if pending > 5 and delivering < len(self.couriers_data) / 2:
            self.log("⚠️ Координатор: много ожидающих заказов, активирую всех курьеров!")
            self.activate_all_couriers()

        # Проверяем застрявшие заказы
        for conversation_id, conv in list(self.active_conversations.items()):
            if time.time() - conv["start_time"] > 30:  # 30 секунд без прогресса
                self.log(f"⏰ Координатор: обсуждение {conversation_id} застряло, закрываю")
                del self.active_conversations[conversation_id]

    def activate_all_couriers(self):
        """Активирует всех доступных курьеров"""
        for courier_id, status in self.courier_status.items():
            if status == "available":
                courier = next((c for c in self.couriers_data if str(c['id']) == courier_id), None)
                if courier:
                    self.send_message(f"courier_{courier_id}", {
                        "type": "activation_request",
                        "reason": "Много ожидающих заказов",
                        "available_orders": len(self.pending_orders)
                    })

    def broadcast_system_info(self):
        """Рассылает информацию о системе всем курьерам"""
        system_info = {
            "type": "system_broadcast",
            "pending_orders": len(self.pending_orders),
            "delivered_orders": len(self.delivered_orders),
            "active_couriers": sum(1 for s in self.courier_status.values()
                                   if s == "delivering"),
            "system_load": self.calculate_system_load(),
            "timestamp": time.time()
        }

        for courier in self.couriers_data:
            self.send_message(f"courier_{courier['id']}", system_info)

        self.log(f"📢 Координатор: разослал системную информацию")

    def notify_couriers_about_load(self):
        """Уведомляет курьеров о текущей загрузке"""
        load_info = {
            "type": "load_info",
            "timestamp": time.time(),
            "courier_loads": {}
        }

        for courier in self.couriers_data:
            courier_id = str(courier['id'])
            load_info["courier_loads"][courier_id] = {
                "name": courier['name'],
                "current_load": self.courier_load.get(courier_id, 0.0),
                "max_capacity": courier['max_capacity'],
                "utilization": (self.courier_load.get(courier_id, 0.0) / courier['max_capacity']) * 100
            }

        # Рассылаем информацию о загрузке
        for courier in self.couriers_data:
            self.send_message(f"courier_{courier['id']}", load_info)


class CoordinatorBehaviour(FipaRequestProtocol):
    def __init__(self, agent):
        super().__init__(agent, is_initiator=False)
        self.agent = agent

    def start_coordination(self):
        """Начинает процесс координации распределения заказов"""
        if not self.agent.pending_orders:
            self.agent.log("✅ Все заказы распределены!")
            return

        self.agent.log("🎯 КООРДИНАТОР: НАЧИНАЮ РАСПРЕДЕЛЕНИЕ ЗАКАЗОВ!")

        distributed_count = 0
        coordination_attempts = 0
        max_attempts = len(self.agent.pending_orders) * 3

        # Сначала распределяем срочные заказы
        urgent_orders = [o for o in self.agent.pending_orders
                         if o.get("priority") == "urgent"]
        for order in urgent_orders:
            self.agent.log(f"🚨 СРОЧНЫЙ ЗАКАЗ #{order['id']}! Немедленное распределение!")
            self.process_order_urgently(order)
            distributed_count += 1
            time.sleep(1)

        # Затем остальные заказы
        while self.agent.pending_orders and coordination_attempts < max_attempts:
            order = self.agent.pending_orders[0]
            self.agent.log(f"🔍 Координатор: анализирую заказ #{order['id']} ({order['weight']}кг)")

            courier_id = self.agent.find_best_courier_for_order(order)

            if courier_id:
                self.assign_order_to_courier(order, courier_id)
                distributed_count += 1
                coordination_attempts = 0

                # Обновляем GUI
                self.agent.update_gui_after_distribution()
                self.update_courier_gui(courier_id)

                # Случайно организуем обсуждение
                if random.random() < 0.3:  # 30% шанс
                    self.initiate_courier_discussion(order, courier_id)
            else:
                coordination_attempts += 1
                self.agent.log(f"⏭️ Координатор: временно откладываю заказ #{order['id']}")
                self.agent.pending_orders.append(self.agent.pending_orders.pop(0))
                time.sleep(2)

            coordination_attempts += 1
            time.sleep(1)

        remaining_orders = len(self.agent.pending_orders)
        self.agent.log(f"📊 Координатор завершил работу! "
                       f"Распределено: {distributed_count}, "
                       f"Осталось: {remaining_orders}")

        # Итоговая статистика
        self.agent.log("📈 ИТОГОВАЯ СТАТИСТИКА КООРДИНАЦИИ:")
        for courier in self.agent.couriers_data:
            courier_id = str(courier['id'])
            load = self.agent.courier_load.get(courier_id, 0.0)
            orders_count = len(self.agent.courier_orders.get(courier_id, []))
            capacity = courier['max_capacity']
            utilization = (load / capacity) * 100 if capacity > 0 else 0
            self.agent.log(
                f"   🚗 {courier['name']}: {load:.1f}/{capacity:.1f}кг ({utilization:.1f}%), "
                f"заказов: {orders_count}")

    def process_order_urgently(self, order):
        """Обрабатывает срочный заказ"""
        self.agent.log(f"🚨 Обрабатываю срочный заказ #{order['id']}")

        # Ищем любого доступного курьера
        for courier in self.agent.couriers_data:
            courier_id = str(courier['id'])
            current_load = self.agent.courier_load.get(courier_id, 0.0)
            available_capacity = courier['max_capacity'] - current_load

            if order["weight"] <= available_capacity:
                self.assign_order_to_courier(order, courier_id)
                self.agent.log(f"🚨 СРОЧНО: заказ #{order['id']} назначен курьеру {courier['name']}")
                return True

        self.agent.log(f"❌ Невозможно обработать срочный заказ #{order['id']} - нет свободных курьеров")
        return False

    def initiate_courier_discussion(self, order, assigned_courier_id):
        """Инициирует обсуждение между курьерами"""
        # Находим другого курьера для обсуждения
        other_couriers = [c for c in self.agent.couriers_data
                          if str(c['id']) != assigned_courier_id]

        if other_couriers:
            other_courier = random.choice(other_couriers)

            # Отправляем сообщение для обсуждения маршрута
            self.agent.send_message(f"courier_{assigned_courier_id}", {
                "type": "route_discussion",
                "order_id": order['id'],
                "partner_id": other_courier['id'],
                "message": f"Обсудите оптимальный маршрут для заказа #{order['id']} с курьером {other_courier['name']}"
            })

            self.agent.log(f"💬 Координатор: инициировал обсуждение маршрута для заказа #{order['id']}")

    def assign_order_to_courier(self, order, courier_id):
        """Назначает заказ курьеру"""
        courier_name = next((c['name'] for c in self.agent.couriers_data
                             if str(c['id']) == courier_id), "Неизвестный")

        # Обновляем статус заказа
        self.agent.update_order_status(order['id'], "assigned", courier_name)

        # Отправляем детальное сообщение курьеру
        instruction = self.generate_detailed_instruction(order, courier_name)

        self.agent.send_message(f"courier_{courier_id}", {
            "type": "order_assignment",
            "order": order,
            "coordinator_instruction": instruction,
            "details": {
                "priority": order.get("priority", "normal"),
                "estimated_time": self.estimate_delivery_time(order, courier_id),
                "special_instructions": self.get_special_instructions(order)
            }
        })

        self.agent.pending_orders.remove(order)
        self.agent.assigned_orders.append(order)

        self.agent.log(f"✅ Координатор: заказ #{order['id']} назначен курьеру {courier_name}")
        self.agent.log(f"📝 Инструкция: {instruction}")

    def generate_detailed_instruction(self, order, courier_name):
        """Генерирует детальную инструкцию для курьера"""
        priority = order.get("priority", "normal")
        priority_text = {
            "urgent": "СРОЧНЫЙ ЗАКАЗ! Выполнить немедленно!",
            "high": "Заказ высокого приоритета",
            "normal": "Стандартный заказ"
        }.get(priority, "Стандартный заказ")

        instructions = [
            f"{priority_text}",
            f"Курьер {courier_name}, доставьте заказ #{order['id']}",
            f"Описание: {order['description']}",
            f"Вес: {order['weight']} кг",
            f"Получатель: {order.get('recipient', 'Не указан')}"
        ]

        if order.get("recipient_phone"):
            instructions.append(f"Телефон: {order['recipient_phone']}")

        # Добавляем случайные специальные инструкции
        special_instructions = [
            "Требуется аккуратная транспортировка",
            "Проверить целостность упаковки перед доставкой",
            "Получить подпись получателя",
            "Сфотографировать место доставки",
            "Сообщить получателю о прибытии за 10 минут"
        ]

        if random.random() < 0.5:
            instructions.append(f"📋 {random.choice(special_instructions)}")

        return "\n".join(instructions)

    def estimate_delivery_time(self, order, courier_id):
        """Оценивает время доставки"""
        courier = next((c for c in self.agent.couriers_data
                        if str(c['id']) == courier_id), None)

        if not courier:
            return "Неизвестно"

        # Простая оценка: вес / скорость * коэффициент
        base_time = order["weight"] / 10  # базовое время
        speed_factor = {
            "car": 0.7,
            "motorcycle": 0.8,
            "bicycle": 1.2,
            "foot": 2.0
        }.get(courier['transport_type'], 1.0)

        estimated_minutes = int(base_time * speed_factor * random.uniform(15, 45))
        return f"{estimated_minutes} минут"

    def get_special_instructions(self, order):
        """Возвращает специальные инструкции для заказа"""
        specials = []

        if "лекарств" in order["description"].lower():
            specials.append("Хранить при комнатной температуре")

        if "электроник" in order["description"].lower():
            specials.append("Избегать тряски и ударов")

        if "хрупк" in order["description"].lower():
            specials.append("Обращаться осторожно, хрупкий груз")

        if "документ" in order["description"].lower():
            specials.append("Конфиденциальный груз")

        return specials if specials else ["Стандартные меры предосторожности"]

    def update_courier_gui(self, courier_id):
        """Обновляет данные курьера в GUI"""
        courier = next((c for c in self.agent.couriers_data
                        if str(c['id']) == courier_id), None)
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
                "status": "delivering" if current_load > 0 else "available",
                "location": self.agent.courier_locations.get(courier_id, "база")
            })

    def handle_request(self, message):
        """Обрабатывает входящие запросы"""
        try:
            content = json.loads(message.content)
            msg_type = content.get("type")
            self.agent.log(f"📨 Координатор получил сообщение: {msg_type} от {message.sender.name}")

            if msg_type == "order_accepted":
                self.handle_order_accepted(content)
            elif msg_type == "order_delivered":
                self.handle_order_delivered(content)
            elif msg_type == "help_request":
                self.handle_help_request(content)
            elif msg_type == "info_request":
                self.handle_info_request(content, message.sender.name)
            elif msg_type == "courier_available":
                self.handle_courier_available(content)
            elif msg_type == "available_for_help":
                self.handle_available_for_help(content)
            elif msg_type == "joint_delivery_response":
                self.handle_joint_delivery_response(content)
            elif msg_type == "route_suggestion":
                self.handle_route_suggestion(content, message.sender.name)
            elif msg_type == "problem_report":
                self.handle_problem_report(content, message.sender.name)
            elif msg_type == "resource_info":
                self.handle_resource_info(content, message.sender.name)
            elif msg_type == "advice_request":
                self.handle_advice_request(content, message.sender.name)
            elif msg_type == "meeting_suggestion":
                self.handle_meeting_suggestion(content, message.sender.name)

        except Exception as e:
            self.agent.log(f"❌ Ошибка обработки сообщения: {e}")

    def handle_order_accepted(self, content):
        """Обрабатывает подтверждение принятия заказа"""
        courier_id = content["courier_id"]
        order_id = content["order_id"]
        courier_name = content["courier_name"]

        self.agent.log(f"👍 Курьер {courier_name} подтвердил принятие заказа #{order_id}")

        # Обновляем статус курьера
        self.agent.courier_status[str(courier_id)] = "delivering"
        self.agent.courier_locations[str(courier_id)] = "в пути"

    def handle_order_delivered(self, content):
        """Обрабатывает уведомление о доставке"""
        order_id = content["order_id"]
        courier_name = content["courier_name"]
        courier_id = content["courier_id"]

        # Находим вес заказа
        order_weight = next((order['weight'] for order in self.agent.orders_data
                             if order['id'] == order_id), 0)

        # Добавляем в доставленные
        self.agent.delivered_orders.append(order_id)

        # Обновляем нагрузку курьера
        if str(courier_id) in self.agent.courier_load:
            self.agent.courier_load[str(courier_id)] = max(0, self.agent.courier_load[str(courier_id)] - order_weight)

        # Удаляем заказ из списка курьера
        if str(courier_id) in self.agent.courier_orders and order_id in self.agent.courier_orders[str(courier_id)]:
            self.agent.courier_orders[str(courier_id)].remove(order_id)

        # Обновляем статус заказа
        self.agent.update_order_status(order_id, "delivered", courier_name)

        # Обновляем статус курьера
        self.agent.courier_status[str(courier_id)] = "available"
        self.agent.courier_locations[str(courier_id)] = "база"

        self.agent.log(f"🎉 Координатор: заказ #{order_id} доставлен курьером {courier_name}!")

        # Отправляем поздравление курьеру
        self.agent.send_message(f"courier_{courier_id}", {
            "type": "delivery_congratulations",
            "order_id": order_id,
            "message": f"Отличная работа, {courier_name}! Заказ #{order_id} успешно доставлен."
        })

        # Обновляем GUI
        self.update_courier_gui(courier_id)

        # Обновляем статистику
        self.agent.update_gui_statistics({
            "delivered_orders": len(self.agent.delivered_orders),
            "used_capacity": sum(self.agent.courier_load.values()),
            "pending_orders": len(self.agent.pending_orders),
            "assigned_orders": len(self.agent.assigned_orders) - len(self.agent.delivered_orders),
            "messages_exchanged": len(self.agent.communication_history)
        })

        # Удаляем доставленный заказ
        self.agent.assigned_orders = [order for order in self.agent.assigned_orders
                                      if order['id'] != order_id]

        # Проверяем завершение работы
        if len(self.agent.delivered_orders) == len(self.agent.orders_data):
            self.agent.log("🏁 ВСЕ ЗАКАЗЫ ДОСТАВЛЕНЫ! СИСТЕМА ЗАВЕРШИЛА РАБОТУ!")

            # Рассылаем поздравления всем курьерам
            for courier in self.agent.couriers_data:
                self.agent.send_message(f"courier_{courier['id']}", {
                    "type": "mission_complete",
                    "message": "Все заказы доставлены! Отличная работа команды!"
                })

    def handle_help_request(self, content):
        """Обрабатывает запрос о помощи от курьера"""
        courier_id = content["courier_id"]
        reason = content.get("reason", "не указана")
        order_id = content.get("order_id")

        self.agent.log(f"🆘 Координатор: курьер {courier_id} запрашивает помощь. Причина: {reason}")

        # Создаем тему для помощи
        help_conversation_id = f"help_{courier_id}_{int(time.time())}"

        # Ищем курьера, который может помочь
        available_couriers = []
        for courier in self.agent.couriers_data:
            cid = str(courier['id'])
            if cid != courier_id and self.agent.courier_status.get(cid) == "available":
                available_couriers.append(courier)

        if available_couriers:
            helpers = random.sample(available_couriers, min(2, len(available_couriers)))

            for helper in helpers:
                self.agent.send_message(f"courier_{helper['id']}", {
                    "type": "help_assignment",
                    "helping_courier_id": courier_id,
                    "reason": reason,
                    "order_id": order_id,
                    "conversation_id": help_conversation_id
                })

                self.agent.log(f"🤝 Координатор: направил курьера {helper['name']} на помощь курьеру {courier_id}")

                # Инициируем обсуждение помощи
                self.agent.send_message(f"courier_{courier_id}", {
                    "type": "help_coordination",
                    "helper_id": helper['id'],
                    "helper_name": helper['name'],
                    "conversation_id": help_conversation_id,
                    "message": f"Курьер {helper['name']} направлен вам на помощь. Обсудите детали."
                })
        else:
            self.agent.log(f"⚠️ Координатор: нет доступных курьеров для помощи {courier_id}")
            self.agent.send_message(f"courier_{courier_id}", {
                "type": "help_unavailable",
                "message": "В данный момент нет свободных курьеров для помощи. Попробуйте позже."
            })

    def handle_joint_delivery_response(self, content):
        """Обрабатывает ответ на приглашение к совместной доставке"""
        courier_id = content["courier_id"]
        order_id = content["order_id"]
        response = content.get("response", "unknown")
        conversation_id = content.get("conversation_id")

        if response == "accept":
            self.agent.log(f"✅ Курьер {courier_id} согласился на совместную доставку заказа #{order_id}")

            # Добавляем в активное обсуждение
            if conversation_id in self.agent.active_conversations:
                self.agent.active_conversations[conversation_id]["participants"].append(courier_id)

                # Если набралось 2+ участника, начинаем координацию
                participants = self.agent.active_conversations[conversation_id]["participants"]
                if len(participants) >= 2:
                    self.coordinate_joint_delivery(conversation_id, participants)
        else:
            self.agent.log(f"❌ Курьер {courier_id} отказался от совместной доставки заказа #{order_id}")

    def coordinate_joint_delivery(self, conversation_id, participants):
        """Координирует совместную доставку"""
        conversation = self.agent.active_conversations.get(conversation_id)
        if not conversation:
            return

        order = conversation["order"]

        # Создаем чат для участников
        for i, participant1 in enumerate(participants):
            for participant2 in participants[i + 1:]:
                self.agent.send_message(f"courier_{participant1}", {
                    "type": "joint_delivery_coordination",
                    "partner_id": participant2,
                    "order_id": order['id'],
                    "conversation_id": conversation_id,
                    "message": f"Начинайте обсуждение совместной доставки заказа #{order['id']}"
                })

        self.agent.log(f"💬 Координатор: начал координацию совместной доставки заказа #{order['id']}")

    def handle_route_suggestion(self, content, sender_name):
        """Обрабатывает предложение маршрута от курьера"""
        order_id = content.get("order_id")
        suggestion = content.get("suggestion", "")

        self.agent.log(f"🗺️ Курьер {sender_name} предложил маршрут для заказа #{order_id}: {suggestion}")

        # Пересылаем предложение другим заинтересованным курьерам
        for courier in self.agent.couriers_data:
            if f"courier_{courier['id']}" != sender_name:
                self.agent.send_message(f"courier_{courier['id']}", {
                    "type": "route_suggestion_shared",
                    "order_id": order_id,
                    "suggestion": suggestion,
                    "from_courier": sender_name
                })

    def handle_problem_report(self, content, sender_name):
        """Обрабатывает отчет о проблеме от курьера"""
        problem = content.get("problem", "")
        severity = content.get("severity", "medium")
        order_id = content.get("order_id")

        self.agent.log(f"🚨 ПРОБЛЕМА от {sender_name}: {problem} (серьезность: {severity})")

        if severity == "high":
            # Срочное уведомление всех курьеров
            for courier in self.agent.couriers_data:
                self.agent.send_message(f"courier_{courier['id']}", {
                    "type": "urgent_problem_alert",
                    "problem": problem,
                    "reported_by": sender_name,
                    "order_id": order_id,
                    "message": "ВНИМАНИЕ: Срочная проблема! Будьте осторожны."
                })

    def handle_info_request(self, content, sender_name):
        """Обрабатывает запрос информации от курьера"""
        request_type = content.get("request_type")
        courier_id = content.get("courier_id")

        response = {}
        if request_type == "system_status":
            response = {
                "type": "info_response",
                "pending_orders": len(self.agent.pending_orders),
                "active_couriers": sum(1 for status in self.agent.courier_status.values()
                                       if status in ["delivering", "collecting"]),
                "system_load": self.agent.calculate_system_load(),
                "busiest_courier": self.get_busiest_courier(),
                "timestamp": time.time()
            }
        elif request_type == "courier_status":
            response = {
                "type": "info_response",
                "all_couriers": [
                    {
                        "id": c['id'],
                        "name": c['name'],
                        "status": self.agent.courier_status.get(str(c['id']), "unknown"),
                        "load": self.agent.courier_load.get(str(c['id']), 0.0),
                        "capacity": c['max_capacity'],
                        "location": self.agent.courier_locations.get(str(c['id']), "unknown")
                    }
                    for c in self.agent.couriers_data
                ]
            }

        # Отправляем ответ
        self.agent.send_message(sender_name, response)

    def get_busiest_courier(self):
        """Возвращает самого загруженного курьера"""
        if not self.agent.couriers_data:
            return "Нет данных"

        busiest = max(self.agent.couriers_data,
                      key=lambda c: self.agent.courier_load.get(str(c['id']), 0.0))

        load = self.agent.courier_load.get(str(busiest['id']), 0.0)
        utilization = (load / busiest['max_capacity']) * 100

        return {
            "name": busiest['name'],
            "load": load,
            "utilization": round(utilization, 1),
            "orders": len(self.agent.courier_orders.get(str(busiest['id']), []))
        }

    def handle_courier_available(self, content):
        """Обрабатывает уведомление о доступности курьера"""
        courier_id = content.get("courier_id")
        name = content.get("name", "Курьер")

        self.agent.log(f"✅ Курьер {name} ({courier_id}) сообщил о своей доступности")

        # Приветственное сообщение
        self.agent.send_message(f"courier_{courier_id}", {
            "type": "welcome_message",
            "message": f"Добро пожаловать в систему, {name}! Ожидайте назначения заказов.",
            "system_status": {
                "pending_orders": len(self.agent.pending_orders),
                "active_couriers": len([s for s in self.agent.courier_status.values()
                                        if s == "delivering"])
            }
        })

    def handle_available_for_help(self, content):
        """Обрабатывает уведомление о готовности помочь"""
        courier_id = content.get("courier_id")
        available_capacity = content.get("available_capacity", 0)

        courier = next((c for c in self.agent.couriers_data
                        if str(c['id']) == courier_id), None)

        if courier:
            self.agent.log(f"🤝 Курьер {courier['name']} готов помочь другим. Доступная емкость: {available_capacity}кг")

            # Добавляем в список доступных помощников
            self.agent.send_message(f"courier_{courier_id}", {
                "type": "helper_registered",
                "message": "Вы добавлены в список доступных помощников. Ожидайте запросов на помощь.",
                "available_for_help": True
            })

