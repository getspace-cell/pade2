# [file name]: base_agent.py
from pade.pade.core.agent import Agent
from pade.pade.acl.messages import ACLMessage
from pade.pade.acl.aid import AID
import json
import time
import requests


class BaseAgent(Agent):
    def __init__(self, aid):
        super().__init__(aid=aid)
        self.agent_name = aid.name
        self.start_time = time.time()
        self.gui_url = "http://localhost:8001"

    def send_message(self, receiver_name, content, performative="inform"):
        """Отправка сообщения другому агенту"""
        try:
            message = ACLMessage(performative)
            message.add_receiver(AID(name=receiver_name))
            message.set_content(json.dumps(content))
            super().send(message)
            elapsed = time.time() - self.start_time
            self.log(f"📤 [{elapsed:.1f}s] Отправлено для {receiver_name}: {content.get('type')}")

            # Сразу логируем отправленное сообщение в GUI
            self.log_communication(self.agent_name, receiver_name,
                                   content.get('type'), content, "outgoing")
        except Exception as e:
            elapsed = time.time() - self.start_time
            self.log(f"❌ Ошибка отправки: {e}")

    def log(self, message):
        """Логирование с выводом в консоль и отправкой в GUI"""
        elapsed = time.time() - self.start_time
        log_message = f"[{elapsed:6.1f}s] [{self.agent_name}] {message}"
        print(log_message)

        # Отправляем лог в GUI
        try:
            requests.post(
                f"{self.gui_url}/api/log",
                json={
                    "message": message,
                    "agent": self.agent_name
                },
                timeout=1
            )
        except:
            pass  # GUI может быть не доступен

    def log_communication(self, sender, receiver, msg_type, content, direction="outgoing"):
        """Логирует общение между агентами"""
        try:
            # Форматируем сообщение для GUI
            formatted_msg = {
                "sender": sender,
                "receiver": receiver,
                "type": msg_type,
                "content": content,
                "direction": direction,
                "timestamp": time.time(),
                "time_str": time.strftime("%H:%M:%S", time.localtime())
            }

            requests.post(
                f"{self.gui_url}/api/log_communication",
                json=formatted_msg,
                timeout=1
            )
            self.log(
                f"💬 Сообщение {'отправлено' if direction == 'outgoing' else 'получено'}: {sender} → {receiver}: {msg_type}")
        except Exception as e:
            self.log(f"⚠️ Не удалось отправить сообщение в GUI: {e}")

    def update_gui_courier(self, courier_id, data):
        """Обновление данных курьера в GUI"""
        try:
            # Добавляем timestamp для отслеживания обновлений
            if "timestamp" not in data:
                data["timestamp"] = time.time()

            requests.post(
                f"{self.gui_url}/api/update_courier/{courier_id}",
                json=data,
                timeout=1
            )
        except Exception as e:
            self.log(f"⚠️ Не удалось обновить данные курьера {courier_id}: {e}")

    def update_gui_statistics(self, statistics):
        """Обновление статистики в GUI"""
        try:
            # Добавляем timestamp
            if "timestamp" not in statistics:
                statistics["timestamp"] = time.time()

            requests.post(
                f"{self.gui_url}/api/update_statistics",
                json=statistics,
                timeout=1
            )
        except Exception as e:
            self.log(f"⚠️ Не удалось обновить статистику: {e}")

    def update_order_status(self, order_id, status, courier_name=None):
        """Обновляет статус заказа в GUI"""
        order_data = {
            "status": status,
            "assigned_courier": courier_name,
            "timestamp": time.time()
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
        """Обновляет GUI после распределения (базовый метод)"""
        pass  # Должен быть переопределен в наследниках

    def update_gui_courier_with_load(self, courier_id, data):
        """Обновление данных курьера с информацией о загрузке"""
        try:
            # Рассчитываем утилизацию, если не указана
            if "utilization" not in data and "current_capacity" in data and "data" in data:
                current_capacity = data.get("current_capacity", 0)
                max_capacity = data.get("data", {}).get("max_capacity", 1)
                utilization = (current_capacity / max_capacity * 100) if max_capacity > 0 else 0
                data["utilization"] = utilization
                data["is_overloaded"] = utilization > 80

            requests.post(
                f"{self.gui_url}/api/update_courier/{courier_id}",
                json=data,
                timeout=1
            )
        except Exception as e:
            self.log(f"⚠️ Не удалось обновить данные курьера с нагрузкой {courier_id}: {e}")

    def update_gui_statistics_with_balance(self, statistics):
        """Обновление статистики с данными балансировки"""
        try:
            # Добавляем timestamp и рассчитываем дисбаланс при необходимости
            statistics["timestamp"] = time.time()

            # Если есть данные о загрузке курьеров, рассчитываем дисбаланс
            if "courier_utilizations" in statistics:
                utilizations = statistics["courier_utilizations"]
                if utilizations:
                    mean_util = sum(utilizations) / len(utilizations)
                    variance = sum((u - mean_util) ** 2 for u in utilizations) / len(utilizations)
                    statistics["load_imbalance"] = variance ** 0.5

            requests.post(
                f"{self.gui_url}/api/update_statistics",
                json=statistics,
                timeout=1
            )
        except Exception as e:
            self.log(f"⚠️ Не удалось обновить статистику балансировки: {e}")

    def send_balance_alert(self, courier_id, utilization, message):
        """Отправляет оповещение о балансировке"""
        try:
            alert_data = {
                "type": "balance_alert",
                "courier_id": courier_id,
                "utilization": utilization,
                "message": message,
                "timestamp": time.time(),
                "alert_type": "overload" if utilization > 80 else "underload"
            }

            requests.post(
                f"{self.gui_url}/api/log_communication",
                json={
                    "sender": "system",
                    "receiver": f"courier_{courier_id}",
                    "type": "balance_alert",
                    "content": alert_data,
                    "direction": "system",
                    "timestamp": time.time()
                },
                timeout=1
            )
        except Exception as e:
            self.log(f"⚠️ Не удалось отправить оповещение о балансировке: {e}")

    def broadcast_system_balance(self, system_load, target_load, imbalance):
        """Рассылает информацию о балансе системы"""
        try:
            balance_data = {
                "type": "system_balance_update",
                "system_load": system_load,
                "target_load": target_load,
                "imbalance": imbalance,
                "timestamp": time.time(),
                "status": "good" if imbalance < 15 else "warning" if imbalance < 30 else "critical"
            }

            requests.post(
                f"{self.gui_url}/api/update_statistics",
                json=balance_data,
                timeout=1
            )
        except Exception as e:
            self.log(f"⚠️ Не удалось обновить баланс системы: {e}")