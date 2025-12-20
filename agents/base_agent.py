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
                                   content.get('type'), content)
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

    def log_communication(self, sender, receiver, msg_type, content):
        """Логирует общение между агентами"""
        try:
            # Форматируем сообщение для GUI
            formatted_msg = {
                "sender": sender,
                "receiver": receiver,
                "type": msg_type,
                "content": content,
                "direction": "outgoing" if sender == self.agent_name else "incoming",
                "timestamp": time.time()
            }

            requests.post(
                f"{self.gui_url}/api/log_communication",
                json=formatted_msg,
                timeout=1
            )
            self.log(f"💬 Сообщение от {sender} к {receiver}: {msg_type}")
        except Exception as e:
            self.log(f"⚠️ Не удалось отправить сообщение в GUI: {e}")

    def update_gui_courier(self, courier_id, data):
        """Обновление данных курьера в GUI"""
        try:
            requests.post(
                f"{self.gui_url}/api/update_courier/{courier_id}",
                json=data,
                timeout=1
            )
        except:
            pass

    def update_gui_statistics(self, statistics):
        """Обновление статистики в GUI"""
        try:
            requests.post(
                f"{self.gui_url}/api/update_statistics",
                json=statistics,
                timeout=1
            )
        except:
            pass

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
        """Обновляет GUI после распределения (базовый метод)"""
        pass  # Должен быть переопределен в наследниках