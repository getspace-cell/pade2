# [file name]: coordinator_agent.py
import json
import time
import random
import threading
from agents.base_agent import BaseAgent
from pade.pade.behaviours.protocols import FipaRequestProtocol
from pade.pade.acl.messages import ACLMessage


class CoordinatorAgent(BaseAgent):
    def __init__(self, aid, couriers_data, orders_data, target_load_percent=None):
        super().__init__(aid)
        self.couriers_data = couriers_data
        self.orders_data = orders_data
        self.pending_orders = orders_data.copy()
        self.assigned_orders = []
        self.delivered_orders = []

        if target_load_percent is not None:
            self.target_load_percent = target_load_percent
        else:
            self.target_load_percent = 0.27
        

        # Инициализируем курьеров
        self.courier_status = {}
        self.courier_load = {}
        self.courier_orders = {}
        self.courier_locations = {}
        self.courier_capacity = {}
        self.courier_utilization = {}  # Процент загрузки

        for courier in couriers_data:
            courier_id = str(courier['id'])
            self.courier_status[courier_id] = "available"
            self.courier_load[courier_id] = 0.0
            self.courier_orders[courier_id] = []
            self.courier_locations[courier_id] = "база"
            self.courier_capacity[courier_id] = courier['max_capacity']
            self.courier_utilization[courier_id] = 0.0

        self.behaviours.append(CoordinatorBehaviour(self))
        self.communication_history = []
        self.active_conversations = {}
        self.redistribution_queue = []  # Очередь заказов для перераспределения

        # Словарь для отслеживания предложений передачи с таймерами
        self.transfer_proposals = {}  # {conversation_id: {proposal_data, timestamp, responded}}
        self.transfer_timeout = 10  # Секунд до принудительной передачи

        # Запускаем периодическую активность
        self.start_periodic_activities()

    def start_periodic_activities(self):
        """Запускает периодические активности координатора"""

        def periodic_check():
            while True:
                time.sleep(30)
                self.log("=" * 50)
                self.log("🔄 ПЕРИОДИЧЕСКАЯ ПРОВЕРКА БАЛАНСА")

                # Показываем текущую загрузку всех курьеров
                for courier in self.couriers_data:
                    courier_id = str(courier['id'])
                    load = self.courier_load.get(courier_id, 0.0)
                    capacity = courier['max_capacity']
                    utilization = self.calculate_courier_utilization(courier_id)
                    status = "✅ БАЛАНС" if abs(utilization - self.target_load_percent * 100) < 15 else \
                        "⚠️ ПЕРЕГРУЗКА" if utilization > self.target_load_percent * 100 + 10 else \
                            "📉 НЕДОГРУЗКА" if utilization < self.target_load_percent * 100 - 20 else \
                                "ℹ️ НОРМА"

                    self.log(f"   🚗 {courier['name']}: {load:.1f}/{capacity:.1f}кг ({utilization:.1f}%) [{status}]")

                # Проверяем баланс
                self.check_load_balance()
                self.broadcast_system_info()
                self.check_transfer_timeouts()

        thread = threading.Thread(target=periodic_check, daemon=True)
        thread.start()

    def on_start(self):
        self.log("🎯 Агент координации запущен (стратегия: балансировка нагрузки 80%)")
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
        behaviour.start_balanced_distribution()

    def calculate_courier_utilization(self, courier_id):
        """Рассчитывает процент загрузки курьера"""
        capacity = self.courier_capacity.get(courier_id, 1.0)
        load = self.courier_load.get(courier_id, 0.0)
        utilization = (load / capacity) * 100 if capacity > 0 else 0
        self.courier_utilization[courier_id] = utilization
        return utilization

    def find_courier_for_balanced_load(self, order):
        """Находит курьера для заказа с учетом балансировки нагрузки"""
        # Если заказ уже в процессе перераспределения, возвращаем None
        if order.get('in_redistribution_queue', False):
            return None

        order_weight = order["weight"]
        suitable_couriers = []

        for courier in self.couriers_data:
            courier_id = str(courier['id'])
            current_load = self.courier_load.get(courier_id, 0.0)
            capacity = courier['max_capacity']

            # Проверяем, сможет ли курьер взять заказ
            if current_load + order_weight <= capacity:
                # Рассчитываем, насколько это приблизит курьера к целевой загрузке
                current_utilization = self.calculate_courier_utilization(courier_id)
                new_utilization = ((current_load + order_weight) / capacity) * 100

                # Идеальная загрузка - 80%
                distance_from_target = abs(new_utilization - (self.target_load_percent * 100))

                suitable_couriers.append({
                    "courier": courier,
                    "courier_id": courier_id,
                    "current_load": current_load,
                    "capacity": capacity,
                    "current_utilization": current_utilization,
                    "new_utilization": new_utilization,
                    "distance_from_target": distance_from_target,
                    "priority_score": self.calculate_priority_score(courier, order, current_load)
                })

        if not suitable_couriers:
            self.log(f"❌ Нет подходящих курьеров для заказа #{order['id']} ({order['weight']}кг)")

            # Пытаемся организовать совместную доставку или перераспределение
            self.add_to_redistribution_queue(order)
            return None

        # Выбираем курьера, который ближе всего к целевой загрузке
        best_courier = min(suitable_couriers, key=lambda x: x["distance_from_target"])

        self.log(f"🎯 Заказ #{order['id']} → курьер {best_courier['courier']['name']} "
                 f"(загрузка: {best_courier['current_utilization']:.1f}% → {best_courier['new_utilization']:.1f}%, "
                 f"расстояние от цели: {best_courier['distance_from_target']:.1f}%)")

        return best_courier["courier_id"]

    def calculate_priority_score(self, courier, order, current_load):
        """Рассчитывает приоритетный балл для курьера"""
        score = 0.0

        # Приоритет заказа
        priority_bonus = {
            "urgent": 50,
            "high": 30,
            "normal": 10
        }.get(order.get("priority", "normal"), 5)
        score += priority_bonus

        # Совместимость транспорта
        transport_factor = {
            "car": 1.0,
            "motorcycle": 0.9,
            "bicycle": 0.7,
            "foot": 0.5
        }.get(courier['transport_type'], 0.5)
        score *= transport_factor

        # Загрузка (предпочтение менее загруженным, но не пустым)
        capacity = courier['max_capacity']
        utilization = (current_load / capacity) * 100 if capacity > 0 else 0

        # Идеальная загрузка 80%, поэтому оценка снижается по мере удаления от 80%
        load_score = 100 - abs(utilization - (self.target_load_percent * 100))
        score += load_score * 0.5

        # Случайный фактор
        score += random.uniform(0, 20)

        return score

    def assign_order_to_courier_with_balance(self, order, courier_id):
        """Назначает заказ курьеру с обновлением балансировки"""
        courier = next((c for c in self.couriers_data if str(c['id']) == courier_id), None)
        if not courier:
            return False

        # Обновляем нагрузку
        self.courier_load[courier_id] += order["weight"]
        self.courier_orders[courier_id].append(order['id'])

        # Обновляем статус
        if self.courier_load[courier_id] > 0:
            self.courier_status[courier_id] = "delivering"

        # Обновляем утилизацию
        utilization = self.calculate_courier_utilization(courier_id)

        self.log(f"✅ Назначен заказ #{order['id']} ({order['weight']}кг) → {courier['name']} "
                 f"(Загрузка: {self.courier_load[courier_id]:.1f}/{courier['max_capacity']}кг = {utilization:.1f}%)")

        # Отправляем заказ курьеру
        self.send_order_assignment(order, courier_id)

        # Удаляем из ожидающих, добавляем в назначенные
        if order in self.pending_orders:
            self.pending_orders.remove(order)
        self.assigned_orders.append(order)

        # Обновляем GUI
        self.update_order_status(order['id'], "assigned", courier['name'])
        self.update_courier_gui(courier_id)
        self.update_gui_statistics_after_assignment()

        return True

    def send_order_assignment(self, order, courier_id):
        """Отправляет назначение заказа курьеру"""
        courier = next((c for c in self.couriers_data if str(c['id']) == courier_id), None)
        if not courier:
            return

        instruction = self.generate_balanced_instruction(order, courier)

        self.send_message(f"courier_{courier_id}", {
            "type": "order_assignment",
            "order": order,
            "coordinator_instruction": instruction,
            "details": {
                "priority": order.get("priority", "normal"),
                "estimated_time": self.estimate_delivery_time(order, courier_id),
                "special_instructions": self.get_special_instructions(order),
                "target_load_percent": self.target_load_percent * 100,
                "current_utilization": self.calculate_courier_utilization(courier_id)
            }
        })

    def generate_balanced_instruction(self, order, courier):
        """Генерирует инструкцию с учетом балансировки нагрузки"""
        current_load = self.courier_load.get(str(courier['id']), 0.0)
        capacity = courier['max_capacity']
        utilization = (current_load / capacity) * 100 if capacity > 0 else 0

        instructions = [
            f"🎯 Балансировка нагрузки: Ваша текущая загрузка {utilization:.1f}%",
            f"Целевая загрузка системы: {self.target_load_percent * 100:.0f}%",
            f"Заказ #{order['id']} назначен для достижения баланса",
            f"Описание: {order['description']}",
            f"Вес: {order['weight']} кг",
            f"Получатель: {order.get('recipient', 'Не указан')}"
        ]

        if utilization > self.target_load_percent * 100:
            instructions.append(
                "⚠️  Внимание: Вы перегружены! Рассмотрите возможность передачи части заказов коллегам.")
        elif utilization < self.target_load_percent * 100 * 0.5:
            instructions.append("ℹ️  Вы можете предложить помощь перегруженным коллегам.")

        if order.get("recipient_phone"):
            instructions.append(f"Телефон: {order['recipient_phone']}")

        return "\n".join(instructions)

    def check_load_balance(self):
        """Проверяет баланс нагрузки и инициирует перераспределение"""
        # ИЗМЕНЕНИЕ: Повышаем пороги для активации перераспределения
        overload_threshold = self.target_load_percent * 100 + 10  # 90% (было 85%)
        underload_threshold = self.target_load_percent * 100 - 30  # 50% (было 65%)

        overloaded_couriers = []
        underloaded_couriers = []

        for courier_id in self.courier_utilization:
            utilization = self.courier_utilization[courier_id]

            if utilization > overload_threshold:
                courier = next((c for c in self.couriers_data if str(c['id']) == courier_id), None)
                if courier:
                    overloaded_couriers.append({
                        "id": courier_id,
                        "name": courier['name'],
                        "utilization": utilization,
                        "load": self.courier_load.get(courier_id, 0.0),
                        "capacity": self.courier_capacity.get(courier_id, 1.0),
                        "available_capacity": courier['max_capacity'] - self.courier_load.get(courier_id, 0.0),
                        "orders": self.courier_orders.get(courier_id, [])[:]
                    })

            elif utilization < underload_threshold:
                courier = next((c for c in self.couriers_data if str(c['id']) == courier_id), None)
                if courier:
                    underloaded_couriers.append({
                        "id": courier_id,
                        "name": courier['name'],
                        "utilization": utilization,
                        "load": self.courier_load.get(courier_id, 0.0),
                        "capacity": self.courier_capacity.get(courier_id, 1.0),
                        "available_capacity": courier['max_capacity'] - self.courier_load.get(courier_id, 0.0)
                    })

        # Если есть перегруженные и недогруженные курьеры, инициируем перераспределение
        if overloaded_couriers and underloaded_couriers:
            self.log(f"⚖️  Балансировка: {len(overloaded_couriers)} перегруженных (>90%), "
                     f"{len(underloaded_couriers)} недогруженных (<50%)")
            self.initiate_load_redistribution(overloaded_couriers, underloaded_couriers)
        else:
            self.log(f"📊 Баланс в норме. Перегруженных: {len(overloaded_couriers)}, "
                     f"Недогруженных: {len(underloaded_couriers)}")

    def initiate_load_redistribution(self, overloaded, underloaded):
        """Инициирует перераспределение нагрузки с учетом баланса"""
        self.log("⚖️  ИНИЦИИРУЮ УМНОЕ ПЕРЕРАСПРЕДЕЛЕНИЕ НАГРУЗКИ:")

        # Сортируем перегруженных по степени перегрузки (от самых перегруженных)
        overloaded_sorted = sorted(overloaded, key=lambda x: x['utilization'], reverse=True)

        # Сортируем недогруженных по степени недогрузки (от самых недогруженных)
        underloaded_sorted = sorted(underloaded, key=lambda x: x['utilization'])

        total_transfers = 0

        for overloaded_courier in overloaded_sorted:
            self.log(f"   📊 {overloaded_courier['name']}: {overloaded_courier['utilization']:.1f}% загрузки")

            # Рассчитываем целевую нагрузку для этого курьера после перераспределения
            target_utilization = self.target_load_percent * 100  # 80%
            current_utilization = overloaded_courier['utilization']

            # Сколько процентов нужно сбросить, чтобы достичь целевой нагрузки
            excess_percent = max(0, current_utilization - target_utilization)

            # Если перегрузка менее 5%, пропускаем
            if excess_percent < 5:
                self.log(f"   ⏩ Пропускаем {overloaded_courier['name']} - перегрузка всего {excess_percent:.1f}%")
                continue

            # Рассчитываем сколько кг нужно сбросить
            capacity = overloaded_courier['capacity']
            excess_kg = capacity * (excess_percent / 100)

            self.log(f"   📉 Нужно сбросить {excess_kg:.1f}кг ({excess_percent:.1f}%) для достижения 80%")

            # Сортируем заказы по весу (от самых тяжелых)
            order_ids_sorted = sorted(
                overloaded_courier['orders'],
                key=lambda oid: self.get_order_weight(oid),
                reverse=True
            )

            # Подбираем заказы для передачи
            transferred_kg = 0
            orders_to_transfer = []

            for order_id in order_ids_sorted:
                order_weight = self.get_order_weight(order_id)

                # Если добавление этого заказа не превысит необходимый сброс
                if transferred_kg + order_weight <= excess_kg:
                    order = next((o for o in self.assigned_orders if o['id'] == order_id), None)
                    if order:
                        orders_to_transfer.append({
                            'order': order,
                            'weight': order_weight
                        })
                        transferred_kg += order_weight

                        # Если достигли нужного сброса, выходим
                        if transferred_kg >= excess_kg * 0.8:  # Сбрасываем 80% от избытка
                            break

            if not orders_to_transfer:
                self.log(f"   ❌ Нет подходящих заказов для передачи от {overloaded_courier['name']}")
                continue

            self.log(f"   📤 Подготовлено к передаче {len(orders_to_transfer)} заказов ({transferred_kg:.1f}кг)")

            # Распределяем заказы между недогруженными курьерами
            for transfer_data in orders_to_transfer:
                order = transfer_data['order']
                order_weight = transfer_data['weight']

                # Ищем лучшего кандидата для получения заказа
                best_candidate = None
                best_score = -float('inf')

                for underloaded_courier in underloaded_sorted:
                    # Проверяем вместимость
                    available_capacity = underloaded_courier['available_capacity']
                    if order_weight > available_capacity:
                        continue

                    # Рассчитываем новую загрузку
                    current_load = self.courier_load.get(underloaded_courier['id'], 0.0)
                    new_utilization = ((current_load + order_weight) / underloaded_courier['capacity']) * 100

                    # Оценка кандидата: насколько близко к 80% он будет после получения
                    distance_from_target = abs(new_utilization - target_utilization)

                    # Предпочтение тем, кто станет ближе к 80%
                    score = 100 - distance_from_target

                    # Бонус за меньшую текущую загрузку (чтобы распределять равномерно)
                    score += (target_utilization - underloaded_courier['utilization']) * 0.5

                    if score > best_score:
                        best_score = score
                        best_candidate = underloaded_courier

                if best_candidate:
                    # Предлагаем передачу
                    success = self.propose_order_transfer(
                        overloaded_courier['id'],
                        best_candidate['id'],
                        order
                    )

                    if success:
                        total_transfers += 1

                        # Обновляем доступную емкость кандидата
                        best_candidate['available_capacity'] -= order_weight

                        # Обновляем загрузку кандидата для следующих итераций
                        best_candidate['utilization'] = ((self.courier_load.get(best_candidate['id'],
                                                                                0.0) + order_weight)
                                                         / best_candidate['capacity']) * 100

                        # Пересортировываем недогруженных
                        underloaded_sorted = sorted(underloaded_sorted, key=lambda x: x['utilization'])

                        self.log(f"   ➡️  Заказ #{order['id']} ({order_weight}кг) предложен {best_candidate['name']}")
                    else:
                        self.log(f"   ❌ Не удалось предложить передачу заказа #{order['id']}")

            # Ограничиваем общее количество передач за один цикл
            if total_transfers >= 3:
                self.log(f"   ⏸️  Достигнут лимит в {total_transfers} передач за цикл")
                break

        if total_transfers == 0:
            self.log("   ✅ Все курьеры уже сбалансированы!")
        else:
            self.log(f"   📊 Всего предложено передач: {total_transfers}")

    def get_order_weight(self, order_id):
        """Получает вес заказа по ID"""
        order = next((o for o in self.assigned_orders if o['id'] == order_id), None)
        return order['weight'] if order else 0

    def propose_order_transfer(self, from_courier_id, to_courier_id, order):
        """Предлагает передачу заказа между курьерами с таймером автоматической передачи"""
        from_courier = next((c for c in self.couriers_data if str(c['id']) == from_courier_id), None)
        to_courier = next((c for c in self.couriers_data if str(c['id']) == to_courier_id), None)

        if not from_courier or not to_courier:
            return

        conversation_id = f"transfer_{order['id']}_{int(time.time())}_{random.randint(1000, 9999)}"

        # Сохраняем предложение для отслеживания таймаута
        self.transfer_proposals[conversation_id] = {
            "order": order,
            "order_id": order['id'],
            "from_courier_id": from_courier_id,
            "to_courier_id": to_courier_id,
            "from_courier_name": from_courier['name'],
            "to_courier_name": to_courier['name'],
            "timestamp": time.time(),
            "responded": False,
            "completed": False
        }

        # ИЗМЕНЕНИЕ: Сообщаем обоим курьерам как от курьера к курьеру (а не от координатора)

        # Отправляем от имени отправителя получателю
        self.send_message(f"courier_{to_courier_id}", {
            "type": "transfer_proposal_incoming",
            "order": order,
            "from_courier_id": from_courier_id,
            "from_courier_name": from_courier['name'],
            "conversation_id": conversation_id,
            "reason": f"Балансировка нагрузки: можете принять дополнительный заказ",
            "message": f"Курьер {from_courier['name']} предлагает передать вам заказ #{order['id']} ({order['weight']}кг)",
            # ИЗМЕНЕНИЕ: Добавляем флаг, что это сообщение от курьера
            "from_courier": f"courier_{from_courier_id}",
            "is_direct": True
        })

        # ИЗМЕНЕНИЕ: Отправляем отправителю уведомление о его предложении
        self.send_message(f"courier_{from_courier_id}", {
            "type": "transfer_proposal_outgoing",
            "order": order,
            "to_courier_id": to_courier_id,
            "to_courier_name": to_courier['name'],
            "conversation_id": conversation_id,
            "reason": f"Балансировка нагрузки: ваша загрузка {self.courier_utilization.get(from_courier_id, 0):.1f}%",
            "message": f"Вы предложили передать заказ #{order['id']} курьеру {to_courier['name']} для балансировки нагрузки",
            # ИЗМЕНЕНИЕ: Добавляем флаг, что это сообщение от курьера
            "to_courier": f"courier_{to_courier_id}",
            "is_direct": True
        })

        self.log(
            f"🤝 Предложена передача заказа #{order['id']} ({order['weight']}кг) от {from_courier['name']} к {to_courier['name']}")
        self.log(
            f"   📊 {from_courier['name']}: {self.courier_utilization.get(from_courier_id, 0):.1f}% → {((self.courier_load.get(from_courier_id, 0.0) - order['weight']) / self.courier_capacity.get(from_courier_id, 1.0) * 100):.1f}%")
        self.log(
            f"   📊 {to_courier['name']}: {self.courier_utilization.get(to_courier_id, 0):.1f}% → {((self.courier_load.get(to_courier_id, 0.0) + order['weight']) / self.courier_capacity.get(to_courier_id, 1.0) * 100):.1f}%")

        return True

    def check_transfer_timeouts(self):
        """Проверяет просроченные предложения передачи и выполняет автоматическую передачу"""
        current_time = time.time()

        for conv_id, proposal in list(self.transfer_proposals.items()):
            # Если прошло больше 10 секунд и нет ответа, и передача не завершена
            if (current_time - proposal["timestamp"] > self.transfer_timeout and
                    not proposal["responded"] and
                    not proposal["completed"]):
                # УДАЛЕНО: лишнее логирование
                # self.log(f"⏰ Автоматическая передача заказа #{proposal['order_id']} через {self.transfer_timeout} секунд")

                # Помечаем как ответившего, чтобы избежать повторной обработки
                proposal["responded"] = True
                proposal["completed"] = True

                # Выполняем автоматическую передачу
                self.execute_automatic_transfer(proposal)

    def execute_automatic_transfer(self, proposal):
        """Выполняет автоматическую передачу заказа после тайм-аута"""
        order = proposal["order"]
        from_courier_id = proposal["from_courier_id"]
        to_courier_id = proposal["to_courier_id"]
        from_name = proposal["from_courier_name"]
        to_name = proposal["to_courier_name"]
        order_id = order['id']

        # Проверяем, что заказ все еще у отправителя
        if order_id not in self.courier_orders.get(from_courier_id, []):
            # УДАЛЕНО: лишнее логирование
            # self.log(f"❌ Автоматическая передача невозможна: заказ #{order_id} уже не у курьера {from_name}")
            return False

        # Проверяем, может ли получатель принять заказ
        available_capacity = self.courier_capacity.get(to_courier_id, 1.0) - self.courier_load.get(to_courier_id, 0.0)
        if order['weight'] > available_capacity:
            # УДАЛЕНО: лишнее логирование
            # self.log(f"❌ Автоматическая передача невозможна: {to_name} не может принять заказ #{order_id} - недостаточно места")
            return False

        # ВЫПОЛНЯЕМ АВТОМАТИЧЕСКУЮ ПЕРЕДАЧУ
        # 1. Убираем заказ у отправителя
        if order_id in self.courier_orders.get(from_courier_id, []):
            self.courier_orders[from_courier_id].remove(order_id)
        self.courier_load[from_courier_id] -= order['weight']

        # 2. Добавляем заказ получателю
        self.courier_orders[to_courier_id].append(order_id)
        self.courier_load[to_courier_id] += order['weight']

        # 3. Обновляем статус курьеров
        self.calculate_courier_utilization(from_courier_id)
        self.calculate_courier_utilization(to_courier_id)

        # 4. Обновляем статус заказа в GUI
        self.update_order_status(order_id, "assigned", to_name)

        # 5. Обновляем GUI курьеров
        self.update_courier_gui(from_courier_id)
        self.update_courier_gui(to_courier_id)

        # 6. Уведомляем обоих курьеров о рекомендации передачи
        self.send_message(f"courier_{from_courier_id}", {
            "type": "transfer_recommendation",
            "order_id": order_id,
            "to_courier_name": to_name,
            "to_courier_id": to_courier_id,
            "message": f"Рекомендую передать заказ #{order_id} курьеру {to_name} для балансировки нагрузки",
            "reason": f"Ваша загрузка: {self.courier_utilization.get(from_courier_id, 0):.1f}%, его: {self.courier_utilization.get(to_courier_id, 0):.1f}%"
        })

        self.send_message(f"courier_{to_courier_id}", {
            "type": "transfer_opportunity",
            "order_id": order_id,
            "from_courier_name": from_name,
            "from_courier_id": from_courier_id,
            "message": f"Курьер {from_name} может передать вам заказ #{order_id} для балансировки нагрузки",
            "reason": f"Его загрузка: {self.courier_utilization.get(from_courier_id, 0):.1f}%, ваша: {self.courier_utilization.get(to_courier_id, 0):.1f}%"
        })

        # УДАЛЕНО: лишнее логирование
        # self.log(f"🤝 КУРЬЕРЫ ДОГОВОРИЛИСЬ: #{order_id} от {from_name} к {to_name}")
        # self.log(f"   📊 {from_name}: {self.courier_utilization.get(from_courier_id, 0):.1f}% → {self.courier_utilization.get(from_courier_id, 0):.1f}%")
        # self.log(f"   📊 {to_name}: {self.courier_utilization.get(to_courier_id, 0):.1f}% → {self.courier_utilization.get(to_courier_id, 0):.1f}%")

        # 7. Обновляем статистику
        self.update_gui_statistics_after_assignment()

        return True

    def add_to_redistribution_queue(self, order):
        """Добавляет заказ в очередь перераспределения"""
        # Проверяем, не находится ли заказ уже в очереди
        if order not in self.redistribution_queue:
            self.redistribution_queue.append(order)
            self.log(f"📥 Заказ #{order['id']} добавлен в очередь перераспределения")

            # Устанавливаем флаг, что заказ находится в очереди
            order['in_redistribution_queue'] = True
            order['added_to_queue_time'] = time.time()

    def attempt_redistribution(self):
        """Пытается перераспределить заказы из очереди"""
        if not self.redistribution_queue:
            return

        self.log(f"🔄 Попытка перераспределения {len(self.redistribution_queue)} заказов из очереди")

        redistributed = []
        failed_orders = []

        # Проходим по копии очереди
        for order in list(self.redistribution_queue):
            # Пропускаем заказы, которые уже находятся в процессе перераспределения
            if order.get('redistribution_attempted', False):
                continue

            order['redistribution_attempted'] = True
            courier_id = self.find_courier_for_balanced_load(order)

            if courier_id:
                if self.assign_order_to_courier_with_balance(order, courier_id):
                    redistributed.append(order)
                    # Удаляем из очереди перераспределения
                    self.redistribution_queue.remove(order)
                    # Сбрасываем флаги
                    order.pop('in_redistribution_queue', None)
                    order.pop('redistribution_attempted', None)
                    order.pop('added_to_queue_time', None)
                else:
                    failed_orders.append(order)
            else:
                failed_orders.append(order)

        if redistributed:
            self.log(f"✅ Успешно перераспределено {len(redistributed)} заказов")
        else:
            self.log(f"⚠️  Не удалось перераспределить заказы из очереди")

        # Если есть неудачные заказы, ограничиваем количество попыток
        for order in failed_orders:
            # Считаем количество попыток
            order['redistribution_attempts'] = order.get('redistribution_attempts', 0) + 1

            if order['redistribution_attempts'] > 3:
                # Удаляем заказ из очереди после 3 неудачных попыток
                if order in self.redistribution_queue:
                    self.redistribution_queue.remove(order)
                self.log(f"❌ Заказ #{order['id']} удален из очереди после 3 неудачных попыток")

    def check_for_redistribution(self):
        """Периодически проверяет возможность перераспределения"""
        if self.redistribution_queue:
            # Очищаем очередь от старых записей
            self.cleanup_redistribution_queue()

            # Пытаемся перераспределить
            self.attempt_redistribution()

    def cleanup_redistribution_queue(self):
        """Очищает очередь перераспределения от старых или безнадежных заказов"""
        if not self.redistribution_queue:
            return

        cleaned_count = 0
        current_time = time.time()

        for order in list(self.redistribution_queue):
            # Удаляем заказы, которые находятся в очереди слишком долго (больше 60 секунд)
            if order.get('added_to_queue_time', 0) > 0:
                if current_time - order['added_to_queue_time'] > 60:
                    self.redistribution_queue.remove(order)
                    cleaned_count += 1
                    self.log(f"🧹 Удален устаревший заказ #{order['id']} из очереди перераспределения")

            # Удаляем заказы с слишком большим количеством неудачных попыток
            elif order.get('redistribution_attempts', 0) > 5:
                self.redistribution_queue.remove(order)
                cleaned_count += 1
                self.log(f"🧹 Удален заказ #{order['id']} после 5 неудачных попыток перераспределения")

        if cleaned_count > 0:
            self.log(f"🧹 Очищено {cleaned_count} заказов из очереди перераспределения")

    def process_order_transfer(self, from_courier_id, to_courier_id, order_id):
        """Обрабатывает подтвержденную передачу заказа"""
        # Находим заказ
        order = next((o for o in self.assigned_orders if o['id'] == order_id), None)
        if not order:
            return False

        from_courier = next((c for c in self.couriers_data if str(c['id']) == from_courier_id), None)
        to_courier = next((c for c in self.couriers_data if str(c['id']) == to_courier_id), None)

        if not from_courier or not to_courier:
            return False

        # Обновляем нагрузку
        self.courier_load[from_courier_id] -= order["weight"]
        self.courier_load[to_courier_id] += order["weight"]

        # Обновляем списки заказов
        if order_id in self.courier_orders.get(from_courier_id, []):
            self.courier_orders[from_courier_id].remove(order_id)

        self.courier_orders[to_courier_id].append(order_id)

        # Обновляем утилизацию
        from_util = self.calculate_courier_utilization(from_courier_id)
        to_util = self.calculate_courier_utilization(to_courier_id)

        self.log(f"🔄 Заказ #{order_id} передан от {from_courier['name']} к {to_courier['name']}")
        self.log(f"   📊 {from_courier['name']}: {from_util:.1f}%")
        self.log(f"   📊 {to_courier['name']}: {to_util:.1f}%")

        # Обновляем статус заказа
        self.update_order_status(order_id, "assigned", to_courier['name'])

        # Обновляем GUI курьеров
        self.update_courier_gui(from_courier_id)
        self.update_courier_gui(to_courier_id)

        # Уведомляем обоих курьеров
        self.send_message(f"courier_{from_courier_id}", {
            "type": "transfer_completed_outgoing",
            "order_id": order_id,
            "to_courier_name": to_courier['name'],
            "message": f"Заказ #{order_id} успешно передан курьеру {to_courier['name']}"
        })

        self.send_message(f"courier_{to_courier_id}", {
            "type": "transfer_completed_incoming",
            "order_id": order_id,
            "from_courier_name": from_courier['name'],
            "message": f"Заказ #{order_id} успешно получен от курьера {from_courier['name']}"
        })

        return True

    def process_transfer_agreement(self, content):
        """Обрабатывает согласие на передачу и выполняет фактическую передачу"""
        from_courier_id = content.get("from_courier_id")
        to_courier_id = content.get("to_courier_id")
        order_id = content.get("order_id")
        conversation_id = content.get("conversation_id")
        from_courier_name = content.get("from_courier_name", "Коллега")
        to_courier_name = content.get("to_courier_name", "Коллега")

        # УДАЛЕНО: лишнее логирование
        # self.log(f"🤝 Получено согласие на передачу: {from_courier_id} → {to_courier_id}, заказ #{order_id}")

        # Обновляем статус предложения передачи
        if conversation_id in self.transfer_proposals:
            self.transfer_proposals[conversation_id]["responded"] = True
            self.transfer_proposals[conversation_id]["completed"] = True

        # Находим заказ
        order = None
        for assigned_order in self.assigned_orders:
            if assigned_order['id'] == order_id:
                order = assigned_order
                break

        if not order:
            # УДАЛЕНО: лишнее логирование
            # self.log(f"❌ Заказ #{order_id} не найден в назначенных")
            return

        # Находим курьеров
        from_courier = next((c for c in self.couriers_data if str(c['id']) == from_courier_id), None)
        to_courier = next((c for c in self.couriers_data if str(c['id']) == to_courier_id), None)

        if not from_courier or not to_courier:
            # УДАЛЕНО: лишнее логирование
            # self.log(f"❌ Не найден один из курьеров")
            return

        # Проверяем, может ли получатель принять заказ
        available_capacity = to_courier['max_capacity'] - self.courier_load.get(to_courier_id, 0.0)
        if order['weight'] > available_capacity:
            # УДАЛЕНО: лишнее логирование
            # self.log(f"❌ {to_courier['name']} не может принять заказ #{order_id} - недостаточно места")
            return

        # ВЫПОЛНЯЕМ ФАКТИЧЕСКУЮ ПЕРЕДАЧУ
        # 1. Убираем заказ у отправителя
        if order_id in self.courier_orders.get(from_courier_id, []):
            self.courier_orders[from_courier_id].remove(order_id)
        self.courier_load[from_courier_id] -= order['weight']

        # 2. Добавляем заказ получателю
        self.courier_orders[to_courier_id].append(order_id)
        self.courier_load[to_courier_id] += order['weight']

        # 3. Обновляем статус курьеров
        self.calculate_courier_utilization(from_courier_id)
        self.calculate_courier_utilization(to_courier_id)

        # 4. Обновляем статус заказа в GUI
        self.update_order_status(order_id, "assigned", to_courier['name'])

        # 5. Обновляем GUI курьеров
        self.update_courier_gui(from_courier_id)
        self.update_courier_gui(to_courier_id)

        # 6. Уведомляем обоих курьеров об успешной передаче
        self.send_message(f"courier_{from_courier_id}", {
            "type": "transfer_agreed",
            "order_id": order_id,
            "to_courier_name": to_courier['name'],
            "message": f"Курьер {to_courier['name']} согласился принять заказ #{order_id} по вашей рекомендации"
        })

        self.send_message(f"courier_{to_courier_id}", {
            "type": "transfer_accepted",
            "order_id": order_id,
            "from_courier_name": from_courier['name'],
            "message": f"Вы приняли заказ #{order_id} от курьера {from_courier['name']} по взаимной договоренности"
        })

        # УДАЛЕНО: лишнее логирование
        # self.log(f"✅ ФАКТИЧЕСКАЯ ПЕРЕДАЧА ВЫПОЛНЕНА: #{order_id} от {from_courier['name']} к {to_courier['name']}")
        # self.log(f"   📊 {from_courier['name']}: {self.courier_utilization.get(from_courier_id, 0):.1f}%")
        # self.log(f"   📊 {to_courier['name']}: {self.courier_utilization.get(to_courier_id, 0):.1f}%")

        # 7. Обновляем статистику
        self.update_gui_statistics_after_assignment()

    def update_courier_gui(self, courier_id):
        """Обновляет данные курьера в GUI"""
        courier = next((c for c in self.couriers_data if str(c['id']) == courier_id), None)
        if courier:
            current_load = self.courier_load.get(courier_id, 0.0)
            assigned_orders = self.courier_orders.get(courier_id, [])
            utilization = self.calculate_courier_utilization(courier_id)

            self.update_gui_courier(courier_id, {
                "data": {
                    "id": courier['id'],
                    "name": courier['name'],
                    "transport_type": courier['transport_type'],
                    "max_capacity": courier['max_capacity']
                },
                "current_capacity": current_load,
                "assigned_orders": assigned_orders,
                "status": "delivering" if current_load > 0 else "available",
                "location": self.courier_locations.get(courier_id, "база"),
                "utilization": utilization,
                "is_overloaded": utilization > self.target_load_percent * 100 + 10
            })

    def update_gui_statistics_after_assignment(self):
        """Обновляет GUI после назначения заказа"""
        total_capacity = sum(courier['max_capacity'] for courier in self.couriers_data)
        used_capacity = sum(self.courier_load.values())
        system_load = (used_capacity / total_capacity * 100) if total_capacity > 0 else 0

        # Рассчитываем дисбаланс (стандартное отклонение утилизации)
        utilizations = list(self.courier_utilization.values())
        if utilizations:
            mean_util = sum(utilizations) / len(utilizations)
            variance = sum((u - mean_util) ** 2 for u in utilizations) / len(utilizations)
            imbalance = variance ** 0.5
        else:
            imbalance = 0

        self.update_gui_statistics({
            "pending_orders": len(self.pending_orders),
            "assigned_orders": len(self.assigned_orders),
            "delivered_orders": len(self.delivered_orders),
            "used_capacity": used_capacity,
            "system_load": system_load,
            "messages_exchanged": len(self.communication_history),
            "load_imbalance": imbalance,
            "target_load": self.target_load_percent * 100,
            "active_couriers": len([s for s in self.courier_status.values() if s == "delivering"])
        })

    def calculate_system_load(self):
        """Рассчитывает загрузку системы"""
        total_capacity = sum(courier['max_capacity'] for courier in self.couriers_data)
        used_capacity = sum(self.courier_load.values())
        return (used_capacity / total_capacity * 100) if total_capacity > 0 else 0

    def get_underloaded_couriers(self):
        """Возвращает список недогруженных курьеров"""
        underloaded = []
        for courier_id in self.courier_utilization:
            utilization = self.courier_utilization[courier_id]
            if utilization < self.target_load_percent * 100 - 20:
                courier = next((c for c in self.couriers_data if str(c['id']) == courier_id), None)
                if courier:
                    underloaded.append({
                        "id": courier_id,
                        "name": courier['name'],
                        "utilization": utilization,
                        "available_capacity": self.courier_capacity.get(courier_id, 1.0) - self.courier_load.get(
                            courier_id, 0.0)
                    })
        return underloaded

    def broadcast_system_info(self):
        """Рассылает информацию о системе всем курьерам"""
        system_info = {
            "type": "system_broadcast",
            "pending_orders": len(self.pending_orders),
            "delivered_orders": len(self.delivered_orders),
            "assigned_orders": len(self.assigned_orders),
            "active_couriers": sum(1 for s in self.courier_status.values()
                                   if s == "delivering"),
            "system_load": self.calculate_system_load(),
            "timestamp": time.time(),
            "target_load": self.target_load_percent * 100
        }

        for courier in self.couriers_data:
            self.send_message(f"courier_{courier['id']}", system_info)

        self.log(f"📢 Координатор: разослал системную информацию")

    def estimate_delivery_time(self, order, courier_id):
        """Оценивает время доставки"""
        courier = next((c for c in self.couriers_data if str(c['id']) == courier_id), None)
        if not courier:
            return "Неизвестно"

        base_time = order["weight"] / 10
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

    def handle_order_accepted(self, content):
        """Обрабатывает подтверждение принятия заказа"""
        courier_id = content["courier_id"]
        order_id = content["order_id"]
        courier_name = content["courier_name"]

        self.log(f"👍 Курьер {courier_name} подтвердил принятие заказа #{order_id}")

        # Обновляем статус курьера
        self.courier_status[str(courier_id)] = "delivering"
        self.courier_locations[str(courier_id)] = "в пути"

    def handle_order_delivered(self, content):
        """Обрабатывает уведомление о доставке"""
        order_id = content["order_id"]
        courier_name = content["courier_name"]
        courier_id = content["courier_id"]

        # Находим вес заказа
        order_weight = next((order['weight'] for order in self.orders_data
                             if order['id'] == order_id), 0)

        # Добавляем в доставленные
        self.delivered_orders.append(order_id)

        # Обновляем нагрузку курьера
        if str(courier_id) in self.courier_load:
            self.courier_load[str(courier_id)] = max(0, self.courier_load[str(courier_id)] - order_weight)

        # Удаляем заказ из списка курьера
        if str(courier_id) in self.courier_orders and order_id in self.courier_orders[str(courier_id)]:
            self.courier_orders[str(courier_id)].remove(order_id)

        # Обновляем статус заказа
        self.update_order_status(order_id, "delivered", courier_name)

        # Обновляем статус курьера
        self.courier_status[str(courier_id)] = "available"
        self.courier_locations[str(courier_id)] = "база"

        self.log(f"🎉 Координатор: заказ #{order_id} доставлен курьером {courier_name}!")

        # Отправляем поздравление курьеру
        self.send_message(f"courier_{courier_id}", {
            "type": "delivery_congratulations",
            "order_id": order_id,
            "message": f"Отличная работа, {courier_name}! Заказ #{order_id} успешно доставлен."
        })

        # Обновляем GUI
        self.update_courier_gui(courier_id)

        # Обновляем статистику
        self.update_gui_statistics_after_assignment()

        # Удаляем доставленный заказ
        self.assigned_orders = [order for order in self.assigned_orders
                                if order['id'] != order_id]

        # Проверяем завершение работы
        if len(self.delivered_orders) == len(self.orders_data):
            self.log("🏁 ВСЕ ЗАКАЗЫ ДОСТАВЛЕНЫ! СИСТЕМА ЗАВЕРШИЛА РАБОТУ!")

            # Рассылаем поздравления всем курьерам
            for courier in self.couriers_data:
                self.send_message(f"courier_{courier['id']}", {
                    "type": "mission_complete",
                    "message": "Все заказы доставлены! Отличная работа команды!"
                })

    def handle_help_request(self, content):
        """Обрабатывает запрос о помощи от курьера"""
        courier_id = content["courier_id"]
        reason = content.get("reason", "не указана")
        order_id = content.get("order_id")

        self.log(f"🆘 Координатор: курьер {courier_id} запрашивает помощь. Причина: {reason}")

        # Создаем тему для помощи
        help_conversation_id = f"help_{courier_id}_{int(time.time())}"

        # Ищем курьера, который может помочь
        available_couriers = []
        for courier in self.couriers_data:
            cid = str(courier['id'])
            if cid != courier_id and self.courier_status.get(cid) == "available":
                available_couriers.append(courier)

        if available_couriers:
            helpers = random.sample(available_couriers, min(2, len(available_couriers)))

            for helper in helpers:
                self.send_message(f"courier_{helper['id']}", {
                    "type": "help_assignment",
                    "helping_courier_id": courier_id,
                    "reason": reason,
                    "order_id": order_id,
                    "conversation_id": help_conversation_id
                })

                self.log(f"🤝 Координатор: направил курьера {helper['name']} на помощь курьеру {courier_id}")

                # Инициируем обсуждение помощи
                self.send_message(f"courier_{courier_id}", {
                    "type": "help_coordination",
                    "helper_id": helper['id'],
                    "helper_name": helper['name'],
                    "conversation_id": help_conversation_id,
                    "message": f"Курьер {helper['name']} направлен вам на помощь. Обсудите детали."
                })
        else:
            self.log(f"⚠️ Координатор: нет доступных курьеров для помощи {courier_id}")
            self.send_message(f"courier_{courier_id}", {
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
            self.log(f"✅ Курьер {courier_id} согласился на совместную доставку заказа #{order_id}")

            # Добавляем в активное обсуждение
            if conversation_id in self.active_conversations:
                self.active_conversations[conversation_id]["participants"].append(courier_id)

                # Если набралось 2+ участника, начинаем координацию
                participants = self.active_conversations[conversation_id]["participants"]
                if len(participants) >= 2:
                    self.coordinate_joint_delivery(conversation_id, participants)
        else:
            self.log(f"❌ Курьер {courier_id} отказался от совместной доставки заказа #{order_id}")

    def coordinate_joint_delivery(self, conversation_id, participants):
        """Координирует совместную доставку"""
        conversation = self.active_conversations.get(conversation_id)
        if not conversation:
            return

        order = conversation["order"]

        # Создаем чат для участников
        for i, participant1 in enumerate(participants):
            for participant2 in participants[i + 1:]:
                self.send_message(f"courier_{participant1}", {
                    "type": "joint_delivery_coordination",
                    "partner_id": participant2,
                    "order_id": order['id'],
                    "conversation_id": conversation_id,
                    "message": f"Начинайте обсуждение совместной доставки заказа #{order['id']}"
                })

        self.log(f"💬 Координатор: начал координацию совместной доставки заказа #{order['id']}")

    def handle_transfer_agreement(self, content):
        """Обрабатывает согласие на передачу заказа"""
        from_courier_id = content.get("from_courier_id")
        to_courier_id = content.get("to_courier_id")
        order_id = content.get("order_id")
        conversation_id = content.get("conversation_id")

        self.log(f"🤝 Курьер {to_courier_id} согласился принять заказ #{order_id} от курьера {from_courier_id}")

        # Обрабатываем передачу
        self.process_transfer_agreement(content)

    def handle_transfer_declined(self, content):
        """Обрабатывает отказ от передачи заказа"""
        from_courier_id = content.get("from_courier_id")
        to_courier_id = content.get("to_courier_id")
        order_id = content.get("order_id")
        reason = content.get("reason", "не указана")

        self.log(f"❌ Курьер {to_courier_id} отказался от заказа #{order_id}: {reason}")

        # Уведомляем отправителя об отказе
        self.send_message(f"courier_{from_courier_id}", {
            "type": "transfer_declined_notification",
            "order_id": order_id,
            "to_courier_id": to_courier_id,
            "reason": reason,
            "message": f"Курьер отказался принять заказ #{order_id}"
        })

    def handle_transfer_initiated(self, content):
        """Обрабатывает инициативу передачи заказа от курьера"""
        from_courier_id = content.get("from_courier_id")
        order_id = content.get("order_id")
        reason = content.get("reason", "перегрузка")

        self.log(f"🔄 Курьер {from_courier_id} инициировал передачу заказа #{order_id}: {reason}")

        # Ищем подходящего курьера для передачи
        order = next((o for o in self.assigned_orders if o['id'] == order_id), None)
        if order:
            self.initiate_load_redistribution(
                [{"id": from_courier_id, "orders": [order_id]}],
                self.get_underloaded_couriers()
            )

    def handle_load_info_request(self, content, sender_name):
        """Обрабатывает запрос информации о загрузке"""
        response = {
            "type": "load_info_response",
            "system_load": self.calculate_system_load(),
            "courier_loads": {},
            "target_load": self.target_load_percent * 100,
            "timestamp": time.time()
        }

        for courier in self.couriers_data:
            courier_id = str(courier['id'])
            response["courier_loads"][courier_id] = {
                "name": courier['name'],
                "current_load": self.courier_load.get(courier_id, 0.0),
                "max_capacity": courier['max_capacity'],
                "utilization": self.calculate_courier_utilization(courier_id),
                "status": self.courier_status.get(courier_id, "unknown")
            }

        self.send_message(sender_name, response)

    def handle_courier_available(self, content):
        """Обрабатывает уведомление о доступности курьера"""
        courier_id = content.get("courier_id")
        name = content.get("name", "Курьер")

        self.log(f"✅ Курьер {name} ({courier_id}) сообщил о своей доступности")

        # Приветственное сообщение
        self.send_message(f"courier_{courier_id}", {
            "type": "welcome_message",
            "message": f"Добро пожаловать в систему, {name}! Ожидайте назначения заказов.",
            "system_status": {
                "pending_orders": len(self.pending_orders),
                "active_couriers": len([s for s in self.courier_status.values()
                                        if s == "delivering"])
            }
        })

    def handle_available_for_help(self, content):
        """Обрабатывает уведомление о готовности помочь"""
        courier_id = content.get("courier_id")
        available_capacity = content.get("available_capacity", 0)

        courier = next((c for c in self.couriers_data if str(c['id']) == courier_id), None)

        if courier:
            self.log(f"🤝 Курьер {courier['name']} готов помочь другим. Доступная емкость: {available_capacity}кг")

            # Добавляем в список доступных помощников
            self.send_message(f"courier_{courier_id}", {
                "type": "helper_registered",
                "message": "Вы добавлены в список доступных помощников. Ожидайте запросов на помощь.",
                "available_for_help": True
            })

    def handle_route_suggestion(self, content, sender_name):
        """Обрабатывает предложение маршрута от курьера"""
        order_id = content.get("order_id")
        suggestion = content.get("suggestion", "")

        self.log(f"🗺️ Курьер {sender_name} предложил маршрут для заказа #{order_id}: {suggestion}")

        # Пересылаем предложение другим заинтересованным курьерам
        for courier in self.couriers_data:
            if f"courier_{courier['id']}" != sender_name:
                self.send_message(f"courier_{courier['id']}", {
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

        self.log(f"🚨 ПРОБЛЕМА от {sender_name}: {problem} (серьезность: {severity})")

        if severity == "high":
            # Срочное уведомление всех курьеров
            for courier in self.couriers_data:
                self.send_message(f"courier_{courier['id']}", {
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
                "pending_orders": len(self.pending_orders),
                "active_couriers": sum(1 for status in self.courier_status.values()
                                       if status in ["delivering", "collecting"]),
                "system_load": self.calculate_system_load(),
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
                        "status": self.courier_status.get(str(c['id']), "unknown"),
                        "load": self.courier_load.get(str(c['id']), 0.0),
                        "capacity": c['max_capacity'],
                        "location": self.courier_locations.get(str(c['id']), "unknown")
                    }
                    for c in self.couriers_data
                ]
            }

        # Отправляем ответ
        self.send_message(sender_name, response)

    def get_busiest_courier(self):
        """Возвращает самого загруженного курьера"""
        if not self.couriers_data:
            return "Нет данных"

        busiest = max(self.couriers_data,
                      key=lambda c: self.courier_load.get(str(c['id']), 0.0))

        load = self.courier_load.get(str(busiest['id']), 0.0)
        utilization = (load / busiest['max_capacity']) * 100

        return {
            "name": busiest['name'],
            "load": load,
            "utilization": round(utilization, 1),
            "orders": len(self.courier_orders.get(str(busiest['id']), []))
        }


class CoordinatorBehaviour(FipaRequestProtocol):
    def __init__(self, agent):
        super().__init__(agent, is_initiator=False)
        self.agent = agent

    def start_balanced_distribution(self):
        """Начинает распределение с балансировкой нагрузки"""
        if not self.agent.pending_orders:
            self.agent.log("✅ Нет заказов для распределения")
            return

        self.agent.log("🎯 НАЧИНАЮ БАЛАНСИРОВАННОЕ РАСПРЕДЕЛЕНИЕ ЗАКАЗОВ!")
        self.agent.log(f"🎯 Целевая загрузка системы: {self.agent.target_load_percent * 100:.0f}%")

        distributed_count = 0
        max_attempts = len(self.agent.pending_orders) * 2
        max_redistribution_attempts = 3  # Ограничиваем попытки перераспределения

        # Распределяем срочные заказы в первую очередь
        urgent_orders = [o for o in self.agent.pending_orders if o.get("priority") == "urgent"]
        for order in urgent_orders:
            self.agent.log(f"🚨 СРОЧНЫЙ ЗАКАЗ #{order['id']}! Немедленное распределение!")
            self.process_order_urgently(order)
            distributed_count += 1
            time.sleep(1)

        # Распределяем остальные заказы с балансировкой
        attempts = 0
        while self.agent.pending_orders and attempts < max_attempts:
            attempts += 1
            order = self.agent.pending_orders[0]

            self.agent.log(f"🔍 Анализирую заказ #{order['id']} ({order['weight']}кг) для балансировки")

            courier_id = self.agent.find_courier_for_balanced_load(order)

            if courier_id:
                if self.agent.assign_order_to_courier_with_balance(order, courier_id):
                    distributed_count += 1

                    # Обновляем статистику
                    self.agent.update_gui_statistics_after_assignment()

                    # Инициируем обсуждение между курьерами с вероятностью 30%
                    if random.random() < 0.3:
                        self.initiate_courier_discussion(order, courier_id)
            else:
                self.agent.log(f"⏳ Заказ #{order['id']} временно не может быть распределен")

                # Если есть заказы в очереди перераспределения, пытаемся их обработать
                if self.agent.redistribution_queue:
                    redistribution_attempts = 0
                    while self.agent.redistribution_queue and redistribution_attempts < max_redistribution_attempts:
                        redistribution_attempts += 1
                        self.agent.attempt_redistribution()

                # Перемещаем в конец очереди только если не попал в очередь перераспределения
                if not order.get('in_redistribution_queue', False):
                    self.agent.pending_orders.append(self.agent.pending_orders.pop(0))

            time.sleep(0.5)

        # Выводим итоговую статистику
        self.show_distribution_summary()

    def process_order_urgently(self, order):
        """Обрабатывает срочный заказ"""
        self.agent.log(f"🚨 Обрабатываю срочный заказ #{order['id']}")

        # Ищем курьера с наименьшей загрузкой, который может взять заказ
        best_courier = None
        best_load = float('inf')

        for courier in self.agent.couriers_data:
            courier_id = str(courier['id'])
            current_load = self.agent.courier_load.get(courier_id, 0.0)
            capacity = courier['max_capacity']

            if current_load + order["weight"] <= capacity and current_load < best_load:
                best_courier = courier_id
                best_load = current_load

        if best_courier:
            self.agent.assign_order_to_courier_with_balance(order, best_courier)
            self.agent.log(f"🚨 СРОЧНО: заказ #{order['id']} назначен наименее загруженному курьеру")
            return True

        self.agent.log(f"❌ Невозможно обработать срочный заказ #{order['id']}")
        return False

    def show_distribution_summary(self):
        """Показывает итоговую статистику распределения"""
        self.agent.log("📈 ИТОГОВАЯ СТАТИСТИКА БАЛАНСИРОВКИ:")

        for courier in self.agent.couriers_data:
            courier_id = str(courier['id'])
            load = self.agent.courier_load.get(courier_id, 0.0)
            capacity = courier['max_capacity']
            utilization = self.agent.calculate_courier_utilization(courier_id)
            orders_count = len(self.agent.courier_orders.get(courier_id, []))

            status = "✅ БАЛАНС" if abs(utilization - self.agent.target_load_percent * 100) < 15 else \
                "⚠️ ПЕРЕГРУЗКА" if utilization > self.agent.target_load_percent * 100 + 15 else \
                    "ℹ️ НЕДОГРУЗКА"

            self.agent.log(f"   🚗 {courier['name']}: {load:.1f}/{capacity:.1f}кг ({utilization:.1f}%) "
                           f"[{status}] заказов: {orders_count}")

        total_utilization = sum(self.agent.courier_utilization.values()) / len(
            self.agent.courier_utilization) if self.agent.courier_utilization else 0
        self.agent.log(f"   📊 Средняя загрузка системы: {total_utilization:.1f}%")
        self.agent.log(f"   🎯 Целевая загрузка: {self.agent.target_load_percent * 100:.0f}%")
        self.agent.log(f"   📦 Осталось заказов: {len(self.agent.pending_orders)}")

    def initiate_courier_discussion(self, order, assigned_courier_id):
        """Инициирует обсуждение между курьерами"""
        other_couriers = [c for c in self.agent.couriers_data if str(c['id']) != assigned_courier_id]

        if other_couriers:
            other_courier = random.choice(other_couriers)

            # Отправляем сообщение для обсуждения маршрута или помощи
            self.agent.send_message(f"courier_{assigned_courier_id}", {
                "type": "route_discussion",
                "order_id": order['id'],
                "partner_id": other_courier['id'],
                "message": f"Обсудите оптимальный маршрут для заказа #{order['id']} с курьером {other_courier['name']}"
            })

            self.agent.log(f"💬 Инициировал обсуждение маршрута для заказа #{order['id']}")

    def handle_request(self, message):
        """Обрабатывает входящие запросы"""
        try:
            content = json.loads(message.content)
            msg_type = content.get("type")
            self.agent.log(f"📨 Координатор получил сообщение: {msg_type} от {message.sender.name}")

            if msg_type == "order_accepted":
                self.agent.handle_order_accepted(content)
            elif msg_type == "order_delivered":
                self.agent.handle_order_delivered(content)
            elif msg_type == "help_request":
                self.agent.handle_help_request(content)
            elif msg_type == "transfer_agreement":
                self.agent.process_transfer_agreement(content)  # Используем новый метод
            elif msg_type == "transfer_declined":
                self.agent.handle_transfer_declined(content)
            elif msg_type == "transfer_initiated":
                self.agent.handle_transfer_initiated(content)
            elif msg_type == "load_info_request":
                self.agent.handle_load_info_request(content, message.sender.name)
            elif msg_type == "courier_available":
                self.agent.handle_courier_available(content)
            elif msg_type == "available_for_help":
                self.agent.handle_available_for_help(content)
            elif msg_type == "joint_delivery_response":
                self.agent.handle_joint_delivery_response(content)
            elif msg_type == "route_suggestion":
                self.agent.handle_route_suggestion(content, message.sender.name)
            elif msg_type == "problem_report":
                self.agent.handle_problem_report(content, message.sender.name)
            elif msg_type == "resource_info":
                # Игнорируем сообщения о ресурсах (погода, трафик и т.д.)
                pass
            elif msg_type == "advice_request":
                # Игнорируем запросы советов
                pass
            elif msg_type == "meeting_suggestion":
                # Игнорируем предложения встреч
                pass
            elif msg_type == "info_request":
                self.agent.handle_info_request(content, message.sender.name)
            elif msg_type == "order_declined":
                self.handle_order_declined(content)
            elif msg_type == "overload_warning":
                self.handle_overload_warning(content)
            elif msg_type == "overload_info_request":
                self.handle_overload_info_request(content, message.sender.name)
            elif msg_type == "direct_transfer_initiated":
                self.handle_direct_transfer_initiated(content)

        except Exception as e:
            self.agent.log(f"❌ Ошибка обработки сообщения: {e}")

    def handle_order_declined(self, content):
        """Обрабатывает отказ от заказа"""
        courier_id = content.get("courier_id")
        order_id = content.get("order_id")
        reason = content.get("reason", "не указана")

        self.agent.log(f"❌ Курьер {courier_id} отказался от заказа #{order_id}: {reason}")

        # Возвращаем заказ в очередь
        order = next((o for o in self.agent.assigned_orders if o['id'] == order_id), None)
        if order:
            self.agent.assigned_orders.remove(order)
            self.agent.pending_orders.append(order)
            self.agent.update_order_status(order_id, "pending", None)
            self.agent.log(f"📥 Заказ #{order_id} возвращен в очередь ожидания")

    def handle_overload_warning(self, content):
        """Обрабатывает предупреждение о перегрузке"""
        courier_id = content.get("courier_id")
        utilization = content.get("utilization", 0)
        message = content.get("message", "")

        self.agent.log(f"⚠️  ПРЕДУПРЕЖДЕНИЕ О ПЕРЕГРУЗКЕ: курьер {courier_id} - {utilization:.1f}%")
        self.agent.log(f"   {message}")

        # Запускаем проверку балансировки
        self.agent.check_load_balance()

    def handle_overload_info_request(self, content, sender_name):
        """Обрабатывает запрос информации о перегруженных курьерах"""
        courier_id = content.get("courier_id")
        available_capacity = content.get("available_capacity", 0)

        # Находим перегруженных курьеров
        overloaded = []
        for cid in self.agent.courier_utilization:
            if cid != str(courier_id) and self.agent.courier_utilization[cid] > 80:
                courier = next((c for c in self.agent.couriers_data if str(c['id']) == cid), None)
                if courier:
                    overloaded.append({
                        "id": cid,
                        "name": courier['name'],
                        "utilization": self.agent.courier_utilization[cid],
                        "overload_amount": self.agent.courier_load.get(cid, 0.0) - (courier['max_capacity'] * 0.8)
                    })

        if overloaded:
            # Выбираем самого перегруженного
            most_overloaded = max(overloaded, key=lambda x: x['overload_amount'])

            self.agent.send_message(sender_name, {
                "type": "overload_info_response",
                "most_overloaded": most_overloaded,
                "available_overloaded": overloaded,
                "message": f"Самый перегруженный: {most_overloaded['name']} ({most_overloaded['utilization']:.1f}%)"
            })

            self.agent.log(f"🤝 Предоставил информацию о перегруженных курьерах курьеру {courier_id}")
        else:
            self.agent.send_message(sender_name, {
                "type": "no_overload_info",
                "message": "В системе нет перегруженных курьеров в данный момент"
            })

    def handle_direct_transfer_initiated(self, content):
        """Обрабатывает инициированную напрямую передачу"""
        from_courier_id = content.get("from_courier_id")
        to_courier_id = content.get("to_courier_id")
        order_id = content.get("order_id")

        self.agent.log(f"🤝 Курьер {from_courier_id} договорился с {to_courier_id} о передаче заказа #{order_id}")

        # Подтверждаем передачу
        if self.agent.process_order_transfer(from_courier_id, to_courier_id, order_id):
            self.agent.log(f"✅ Прямая передача заказа #{order_id} подтверждена")