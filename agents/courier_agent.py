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

        self.behaviours.append(CourierCommunicationBehaviour(self))

        # Запускаем периодическую активность
        self.start_periodic_activities()

    def start_periodic_activities(self):
        """Запускает периодические активности курьера"""

        def periodic_activity():
            while True:
                time.sleep(random.randint(15, 30))  # Случайный интервал
                self.random_communication()

        thread = threading.Thread(target=periodic_activity, daemon=True)
        thread.start()

    def on_start(self):
        self.log(f"🚗 Курьер {self.courier_data['name']} запущен. Макс.груз: {self.courier_data['max_capacity']}кг")

        # Представляемся
        self.introduce_to_others()

        # ОБНОВЛЯЕМ GUI ПРИ СТАРТЕ
        self.update_gui()

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
            "helps": self.helps_provided
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

    def offer_help(self, target_courier_id, reason):
        """Предлагает помощь другому курьеру"""
        self.send_message(f"courier_{target_courier_id}", {
            "type": "help_offer",
            "from_courier_id": str(self.courier_data['id']),
            "from_name": self.courier_data['name'],
            "reason": reason,
            "available_capacity": self.courier_data['max_capacity'] - self.current_capacity,
            "location": self.location,
            "message": f"Я могу помочь! {self.generate_help_message()}"
        })

    def generate_help_message(self):
        """Генерирует сообщение с предложением помощи"""
        messages = [
            "У меня есть опыт с подобными ситуациями.",
            "Знаю короткий маршрут в этом районе.",
            "Могу помочь с погрузкой/разгрузкой.",
            "У меня есть необходимое оборудование.",
            "Работаю в этой зоне, могу быстро подъехать.",
            "Свободен в ближайшее время."
        ]
        return random.choice(messages)

    def share_resource_info(self, resource_type, info):
        """Делится информацией о ресурсах с другими курьерами"""
        message_content = {
            "type": "resource_share",
            "resource_type": resource_type,
            "info": info,
            "courier_id": str(self.courier_data['id']),
            "message": f"Делюсь информацией о {resource_type}: {self.generate_resource_message(resource_type)}"
        }

        # Отправляем координатору для распространения
        self.send_message("coordinator_agent", {
            "type": "resource_info",
            "content": message_content
        })

    def generate_resource_message(self, resource_type):
        """Генерирует сообщение о ресурсе"""
        messages = {
            "parking": "Свободные парковочные места у центрального офиса.",
            "traffic": "Пробки на центральной улице, объезжайте через переулки.",
            "weather": "Ожидается дождь, берите дождевики.",
            "roadworks": "Дорожные работы на Ленинском проспекте.",
            "gas_station": "Новая заправка со скидкой 10%.",
            "restaurant": "Кафе 'У курьера' дает скидку 15% на обед.",
            "shortcut": "Нашел короткий путь через промышленную зону."
        }
        return messages.get(resource_type, "Полезная информация")

    def random_communication(self):
        """Случайная коммуникация с другими агентами"""
        if random.random() < 0.4:  # 40% шанс на случайное общение
            activity = random.choice([
                self.share_traffic_info,
                self.ask_for_advice,
                self.share_experience,
                self.report_weather,
                self.suggest_meeting
            ])
            activity()

    def share_traffic_info(self):
        """Делится информацией о трафике"""
        areas = ["центр", "север", "юг", "восток", "запад"]
        conditions = ["пробки", "свободно", "ремонт дороги", "авария", "парад"]

        area = random.choice(areas)
        condition = random.choice(conditions)

        self.share_resource_info("traffic", {
            "area": area,
            "condition": condition,
            "time": time.strftime("%H:%M"),
            "severity": random.choice(["low", "medium", "high"])
        })

    def ask_for_advice(self):
        """Запрашивает совет у других курьеров"""
        questions = [
            "Как лучше доставлять хрупкие грузы?",
            "Есть ли опыт с доставкой в новый район?",
            "Какое лучшее время для доставки в центр?",
            "Как общаться со сложными клиентами?",
            "Какой маршрут лучше для объезда пробок?"
        ]

        self.send_message("coordinator_agent", {
            "type": "advice_request",
            "courier_id": str(self.courier_data['id']),
            "question": random.choice(questions),
            "message": "Нужен совет от опытных коллег!"
        })

    def share_experience(self):
        """Делится опытом"""
        experiences = [
            "Сегодня научился новой технике упаковки.",
            "Нашел отличное приложение для навигации.",
            "Получил благодарность от клиента за быструю доставку.",
            "Разработал систему оптимизации маршрутов.",
            "Прошел курс по безопасному вождению."
        ]

        # Отправляем случайному курьеру
        other_couriers = [c for c in range(1, 6) if c != self.courier_data['id']]
        if other_couriers:
            target = random.choice(other_couriers)
            self.send_message(f"courier_{target}", {
                "type": "experience_share",
                "from_courier_id": str(self.courier_data['id']),
                "experience": random.choice(experiences),
                "message": "Хочу поделиться полезным опытом!"
            })

    def report_weather(self):
        """Сообщает о погоде"""
        weather_conditions = ["солнечно", "дождь", "снег", "туман", "ветрено"]
        self.share_resource_info("weather", {
            "condition": random.choice(weather_conditions),
            "temperature": random.randint(-5, 25),
            "advice": self.get_weather_advice()
        })

    def get_weather_advice(self):
        """Возвращает совет по погоде"""
        return random.choice([
            "Одевайтесь теплее",
            "Возьмите зонт",
            "Будьте осторожны на дороге",
            "Проверьте шины",
            "Снизьте скорость"
        ])

    def suggest_meeting(self):
        """Предлагает встречу"""
        self.send_message("coordinator_agent", {
            "type": "meeting_suggestion",
            "courier_id": str(self.courier_data['id']),
            "purpose": "Обсудить оптимизацию маршрутов",
            "suggested_time": "18:00",
            "location": "Кафе 'У курьера'"
        })


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
            elif msg_type == "help_offer":
                self.handle_help_offer(content)
            elif msg_type == "help_assignment":
                self.handle_help_assignment(content)
            elif msg_type == "help_coordination":
                self.handle_help_coordination(content)
            elif msg_type == "coordination_request":
                self.handle_coordination_request(content)
            elif msg_type == "joint_delivery_invitation":
                self.handle_joint_delivery_invitation(content)
            elif msg_type == "joint_delivery_coordination":
                self.handle_joint_delivery_coordination(content)
            elif msg_type == "route_discussion":
                self.handle_route_discussion(content)
            elif msg_type == "resource_info":
                self.handle_resource_info(content)
            elif msg_type == "info_request":
                self.handle_info_request(content, message.sender.name)
            elif msg_type == "system_broadcast":
                self.handle_system_broadcast(content)
            elif msg_type == "load_info":
                self.handle_load_info(content)
            elif msg_type == "activation_request":
                self.handle_activation_request(content)
            elif msg_type == "delivery_congratulations":
                self.handle_delivery_congratulations(content)
            elif msg_type == "urgent_problem_alert":
                self.handle_urgent_problem_alert(content)
            elif msg_type == "welcome_message":
                self.handle_welcome_message(content)
            elif msg_type == "helper_registered":
                self.handle_helper_registered(content)
            elif msg_type == "route_suggestion_shared":
                self.handle_route_suggestion_shared(content)
            elif msg_type == "experience_share":
                self.handle_experience_share(content)

        except Exception as e:
            self.agent.log(f"❌ Ошибка обработки запроса: {e}")

    def handle_order_assignment(self, content, sender_name):
        """Обрабатываем назначение заказа"""
        order_data = content["order"]
        instruction = content.get("coordinator_instruction", "")
        details = content.get("details", {})

        self.agent.log(f"📨 Получен заказ #{order_data['id']} ({order_data['weight']}кг)")
        self.agent.log(f"📝 Инструкция от координатора: {instruction}")

        if details:
            self.agent.log(f"📋 Детали: Приоритет: {details.get('priority')}, "
                           f"Время доставки: {details.get('estimated_time')}")

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
            self.agent.status = "delivering"
            self.agent.location = "отправляется на загрузку"

            self.agent.log(
                f"✅ Принял заказ #{order_data['id']}. Загрузка: {self.agent.current_capacity}/{self.agent.courier_data['max_capacity']}кг")

            # ОБНОВЛЯЕМ GUI ПОСЛЕ ПРИНЯТИЯ ЗАКАЗА
            self.agent.update_gui()

            # Имитируем доставку
            self.simulate_delivery(order_data, details)
        else:
            self.agent.log(f"❌ Не могу принять заказ #{order_data['id']} - превышена грузоподъемность")

            # Запрашиваем помощь
            self.agent.ask_for_help(
                f"Превышена грузоподъемность для заказа #{order_data['id']} ({order_data['weight']}кг)",
                order_data['id'],
                "high"
            )

    def simulate_delivery(self, order_data, details):
        """Имитируем доставку с взаимодействием с другими курьерами"""

        def deliver():
            # Имитируем время на доставку
            base_time = random.randint(5, 15)  # секунды
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

            # Общаемся во время доставки
            time.sleep(delivery_time / 3)
            self.communicate_during_delivery(order_data)

            time.sleep(delivery_time / 3)

            # Случайно возникают проблемы
            if random.random() < 0.4:  # 40% шанс на проблему
                problem = random.choice([
                    ("пробка на маршруте", "medium"),
                    ("не могу найти адрес", "low"),
                    ("клиент не отвечает", "medium"),
                    ("нужна дополнительная помощь с разгрузкой", "high"),
                    ("поломка транспорта", "high"),
                    ("проблемы с доступом в здание", "low")
                ])

                self.agent.ask_for_help(
                    f"Проблема при доставке заказа #{order_data['id']}: {problem[0]}",
                    order_data['id'],
                    problem[1]
                )
                delivery_time += 3

            time.sleep(delivery_time / 3)
            self.complete_delivery(order_data)

        delivery_thread = threading.Thread(target=deliver, daemon=True)
        delivery_thread.start()

    def communicate_during_delivery(self, order_data):
        """Общается с другими курьерами во время доставки"""
        if random.random() < 0.5:  # 50% шанс
            actions = [
                self.share_route_info,
                self.ask_for_traffic_info,
                self.report_progress
            ]
            action = random.choice(actions)
            action(order_data)

    def share_route_info(self, order_data):
        """Делится информацией о маршруте"""
        route_tips = [
            "Нашел отличный объезд через парк.",
            "Маршрут через набережную быстрее на 10 минут.",
            "Избегайте центра - там парад.",
            "На 5-й улице ремонт, лучше ехать по 3-й.",
            "Мост закрыт, используйте тоннель."
        ]

        # Отправляем координатору
        self.agent.send_message("coordinator_agent", {
            "type": "route_suggestion",
            "courier_id": str(self.agent.courier_data['id']),
            "order_id": order_data['id'],
            "suggestion": random.choice(route_tips),
            "location": self.agent.location
        })

    def ask_for_traffic_info(self, order_data):
        """Запрашивает информацию о трафике"""
        self.agent.send_message("coordinator_agent", {
            "type": "traffic_info_request",
            "courier_id": str(self.agent.courier_data['id']),
            "order_id": order_data['id'],
            "area": "центр",
            "message": "Какая обстановка с трафиком в центре?"
        })

    def report_progress(self, order_data):
        """Сообщает о прогрессе"""
        progress_messages = [
            "Прошел половину маршрута, все по плану.",
            "Забрал груз, отправляюсь к клиенту.",
            "Близко к точке назначения.",
            "Жду подтверждения от клиента.",
            "Нашел место для парковки."
        ]

        self.agent.send_message("coordinator_agent", {
            "type": "progress_report",
            "courier_id": str(self.agent.courier_data['id']),
            "order_id": order_data['id'],
            "progress": random.choice(progress_messages),
            "estimated_arrival": "5-10 минут"
        })

    def complete_delivery(self, order_data):
        """Завершаем доставку"""
        order_id = order_data["id"]
        if order_data in self.agent.current_orders:
            self.agent.current_orders.remove(order_data)
            self.agent.current_capacity -= order_data["weight"]

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

            # Предлагаем помощь другим курьерам
            if random.random() < 0.7:  # 70% шанс
                time.sleep(1)
                self.agent.send_message("coordinator_agent", {
                    "type": "available_for_help",
                    "courier_id": self.agent.courier_data["id"],
                    "available_capacity": self.agent.courier_data["max_capacity"] - self.agent.current_capacity,
                    "message": "Свободен и готов помочь коллегам!"
                })

        # ОБНОВЛЯЕМ GUI ПОСЛЕ ДОСТАВКИ
        self.agent.update_gui()

    def handle_help_offer(self, content):
        """Обрабатывает предложение помощи от другого курьера"""
        from_courier_id = content["from_courier_id"]
        from_name = content.get("from_name", "Коллега")
        reason = content.get("reason", "")
        message = content.get("message", "")

        self.agent.log(f"🤝 {from_name} предлагает помощь: {reason}")
        if message:
            self.agent.log(f"💬 Сообщение: {message}")

        # Отвечаем на предложение
        response = random.choice(["accept", "decline", "discuss"])

        if response == "accept":
            self.agent.log(f"✅ Принимаю помощь от {from_name}")
            self.agent.send_message(f"courier_{from_courier_id}", {
                "type": "help_accepted",
                "courier_id": str(self.agent.courier_data['id']),
                "message": f"Спасибо за предложение! Давайте скоординируем действия.",
                "suggested_meeting": "У входа в офис через 10 минут"
            })
        elif response == "discuss":
            self.agent.log(f"💬 Обсуждаю помощь от {from_name}")
            self.agent.send_message(f"courier_{from_courier_id}", {
                "type": "help_discussion",
                "courier_id": str(self.agent.courier_data['id']),
                "message": "Хорошо, давайте обсудим детали. Какой у вас план?",
                "questions": ["Во сколько можете подъехать?", "Какое у вас оборудование?"]
            })
        else:
            self.agent.log(f"❌ Отклоняю помощь от {from_name} (справлюсь сам)")
            self.agent.send_message(f"courier_{from_courier_id}", {
                "type": "help_declined",
                "courier_id": str(self.agent.courier_data['id']),
                "message": "Спасибо, но я справлюсь самостоятельно."
            })

    def handle_help_assignment(self, content):
        """Обрабатывает назначение помощи от координатора"""
        helping_courier_id = content["helping_courier_id"]
        reason = content.get("reason", "")
        order_id = content.get("order_id")
        conversation_id = content.get("conversation_id")

        self.agent.log(f"🎯 Координатор просит помочь курьеру {helping_courier_id}. Причина: {reason}")
        self.agent.helps_provided += 1

        # Связываемся с курьером, которому нужно помочь
        self.agent.offer_help(helping_courier_id, reason)

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

        # Начинаем обсуждение
        self.agent.send_message(f"courier_{helper_id}", {
            "type": "help_coordination_start",
            "courier_id": str(self.agent.courier_data['id']),
            "conversation_id": conversation_id,
            "message": f"Привет, {helper_name}! Спасибо что откликнулись. Мне нужна помощь с...",
            "my_location": self.agent.location,
            "suggested_plan": self.generate_help_plan()
        })

    def generate_help_plan(self):
        """Генерирует план помощи"""
        plans = [
            "Можете встретить меня у здания и помочь с разгрузкой?",
            "Нужна помощь в поиске адреса, можете подсказать?",
            "Можете подстраховать с тяжелым грузом?",
            "Нужен совет по маршруту в незнакомом районе.",
            "Можете временно принять часть груза?"
        ]
        return random.choice(plans)

    def handle_joint_delivery_invitation(self, content):
        """Обрабатывает приглашение к совместной доставке"""
        order_id = content.get("order_id")
        order_weight = content.get("order_weight")
        order_description = content.get("order_description")
        conversation_id = content.get("conversation_id")
        required_capacity = content.get("required_capacity")

        self.agent.log(f"🤝 Приглашение на совместную доставку заказа #{order_id} ({order_weight}кг)")
        self.agent.log(f"📋 Описание: {order_description}")

        # Принимаем или отклоняем
        available_capacity = self.agent.courier_data["max_capacity"] - self.agent.current_capacity
        response = "accept" if available_capacity >= required_capacity and random.random() < 0.6 else "decline"

        self.agent.send_message("coordinator_agent", {
            "type": "joint_delivery_response",
            "courier_id": str(self.agent.courier_data['id']),
            "order_id": order_id,
            "response": response,
            "conversation_id": conversation_id,
            "available_capacity": available_capacity,
            "message": "Готов к обсуждению!" if response == "accept" else "Не могу участвовать"
        })

    def handle_joint_delivery_coordination(self, content):
        """Обрабатывает координацию совместной доставки"""
        partner_id = content.get("partner_id")
        order_id = content.get("order_id")
        conversation_id = content.get("conversation_id")
        message = content.get("message", "")

        self.agent.log(f"🤝 Координация совместной доставки заказа #{order_id} с курьером {partner_id}")

        # Начинаем обсуждение
        discussion_points = [
            "Как разделим груз?",
            "Кто забирает со склада?",
            "Встречаемся в какой точке?",
            "Кому отчитываемся о доставке?",
            "Какой маршрут оптимальный?"
        ]

        self.agent.send_message(f"courier_{partner_id}", {
            "type": "joint_delivery_discussion",
            "courier_id": str(self.agent.courier_data['id']),
            "order_id": order_id,
            "conversation_id": conversation_id,
            "discussion_points": random.sample(discussion_points, 3),
            "suggestion": "Предлагаю встретиться у центрального входа через 15 минут"
        })

    def handle_route_discussion(self, content):
        """Обрабатывает обсуждение маршрута"""
        order_id = content.get("order_id")
        partner_id = content.get("partner_id")
        message = content.get("message", "")

        self.agent.log(f"🗺️ Обсуждение маршрута для заказа #{order_id} с курьером {partner_id}")

        # Отправляем предложение по маршруту
        routes = [
            "Через центр - быстрее, но есть пробки",
            "По окружной - дольше, но надежнее",
            "Через промзону - короткий, но плохая дорога",
            "Комбинированный маршрут"
        ]

        self.agent.send_message(f"courier_{partner_id}", {
            "type": "route_proposal",
            "courier_id": str(self.agent.courier_data['id']),
            "order_id": order_id,
            "proposed_route": random.choice(routes),
            "reasoning": "Проверил на картах, этот вариант оптимальный",
            "estimated_time": f"{random.randint(15, 45)} минут"
        })

    def handle_resource_info(self, content):
        """Обрабатывает информацию о ресурсах от другого курьера"""
        resource_type = content.get("resource_type")
        info = content.get("info", {})
        message = content.get("message", "")
        sender_id = content.get("courier_id")

        self.agent.log(f"📢 Получил информацию о {resource_type} от курьера {sender_id}")
        if message:
            self.agent.log(f"💬 {message}")

        # Отвечаем с благодарностью
        if random.random() < 0.5:
            self.agent.send_message(f"courier_{sender_id}", {
                "type": "resource_thanks",
                "courier_id": str(self.agent.courier_data['id']),
                "resource_type": resource_type,
                "message": "Спасибо за информацию! Это очень полезно."
            })

    def handle_system_broadcast(self, content):
        """Обрабатывает системную рассылку"""
        pending_orders = content.get("pending_orders", 0)
        delivered_orders = content.get("delivered_orders", 0)
        system_load = content.get("system_load", 0)

        self.agent.log(f"📢 Системная информация: Ожидает {pending_orders} заказов, "
                       f"Доставлено {delivered_orders}, Загрузка системы: {system_load:.1f}%")

        # Можем отреагировать на системную информацию
        if pending_orders > 10 and self.agent.status == "available":
            self.agent.log("⚡ Много ожидающих заказов, предлагаю помощь!")

    def handle_load_info(self, content):
        """Обрабатывает информацию о загрузке курьеров"""
        courier_loads = content.get("courier_loads", {})

        # Находим наименее загруженного курьера (кроме себя)
        my_id = str(self.agent.courier_data['id'])
        other_loads = {cid: data for cid, data in courier_loads.items() if cid != my_id}

        if other_loads:
            least_loaded = min(other_loads.items(), key=lambda x: x[1]["utilization"])
            cid, data = least_loaded

            if data["utilization"] < 30 and self.agent.current_capacity > 0:
                # Предлагаем помощь перегруженным коллегам
                self.agent.log(f"📊 {data['name']} загружен только на {data['utilization']:.1f}%, "
                               f"могу предложить помощь!")

    def handle_activation_request(self, content):
        """Обрабатывает запрос на активацию"""
        reason = content.get("reason", "")
        available_orders = content.get("available_orders", 0)

        self.agent.log(f"🎯 Запрос на активацию: {reason}. Доступно заказов: {available_orders}")

        if self.agent.status == "available":
            self.agent.send_message("coordinator_agent", {
                "type": "activation_response",
                "courier_id": str(self.agent.courier_data['id']),
                "response": "ready",
                "message": "Готов принимать заказы!",
                "available_capacity": self.agent.courier_data["max_capacity"] - self.agent.current_capacity
            })

    def handle_delivery_congratulations(self, content):
        """Обрабатывает поздравление с доставкой"""
        order_id = content.get("order_id")
        message = content.get("message", "")

        self.agent.log(f"🎉 {message}")

        # Отвечаем с благодарностью
        self.agent.send_message("coordinator_agent", {
            "type": "thanks_for_congratulations",
            "courier_id": str(self.agent.courier_data['id']),
            "order_id": order_id,
            "message": "Спасибо! Рад был помочь!"
        })

    def handle_urgent_problem_alert(self, content):
        """Обрабатывает срочное оповещение о проблеме"""
        problem = content.get("problem", "")
        reported_by = content.get("reported_by", "")
        order_id = content.get("order_id")
        message = content.get("message", "")

        self.agent.log(f"🚨 СРОЧНОЕ ОПОВЕЩЕНИЕ: {problem} (сообщил: {reported_by})")
        self.agent.log(f"💬 {message}")

        # Отвечаем, если можем помочь
        if self.agent.status == "available" and random.random() < 0.3:
            self.agent.send_message("coordinator_agent", {
                "type": "urgent_help_offer",
                "courier_id": str(self.agent.courier_data['id']),
                "problem": problem,
                "reported_by": reported_by,
                "message": "Могу помочь! Готов выехать немедленно."
            })

    def handle_welcome_message(self, content):
        """Обрабатывает приветственное сообщение"""
        message = content.get("message", "")
        system_status = content.get("system_status", {})

        self.agent.log(f"👋 {message}")
        self.agent.log(f"📊 Статус системы: {system_status.get('pending_orders', 0)} ожидающих заказов")

    def handle_helper_registered(self, content):
        """Обрабатывает подтверждение регистрации помощника"""
        message = content.get("message", "")

        self.agent.log(f"✅ {message}")

    def handle_route_suggestion_shared(self, content):
        """Обрабатывает общий совет по маршруту"""
        order_id = content.get("order_id")
        suggestion = content.get("suggestion", "")
        from_courier = content.get("from_courier", "")

        self.agent.log(f"🗺️ Совет по маршруту от {from_courier} для заказа #{order_id}: {suggestion}")

        # Можем поблагодарить или предложить свой вариант
        if random.random() < 0.4:
            self.agent.send_message("coordinator_agent", {
                "type": "route_feedback",
                "courier_id": str(self.agent.courier_data['id']),
                "order_id": order_id,
                "suggestion": suggestion,
                "feedback": "Отличный совет! Учту в планировании.",
                "alternative": "Я бы добавил объезд через парк"
            })

    def handle_experience_share(self, content):
        """Обрабатывает обмен опытом"""
        from_courier_id = content.get("from_courier_id")
        experience = content.get("experience", "")
        message = content.get("message", "")

        self.agent.log(f"📚 Обмен опытом от курьера {from_courier_id}: {experience}")

        # Отвечаем с благодарностью и своим опытом
        self.agent.send_message(f"courier_{from_courier_id}", {
            "type": "experience_response",
            "courier_id": str(self.agent.courier_data['id']),
            "message": "Спасибо за опыт! Я тоже недавно узнал что-то полезное...",
            "my_experience": random.choice([
                "Нашел отличное приложение для учета расходов",
                "Узнал про технику безопасной погрузки",
                "Прошел курс по клиентскому сервису"
            ])
        })

    def handle_info_request(self, content, sender_name):
        """Обрабатывает запрос информации"""
        request_type = content.get("request_type")

        response = {}
        if request_type == "status":
            response = {
                "type": "info_response",
                "courier_id": str(self.agent.courier_data['id']),
                "status": self.agent.status,
                "current_load": self.agent.current_capacity,
                "current_orders": len(self.agent.current_orders),
                "location": self.agent.location,
                "available_for_help": self.agent.status == "available"
            }

        # Отправляем ответ
        self.agent.send_message(sender_name, response)

