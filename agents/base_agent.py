from pade.core.agent import Agent
from pade.acl.messages import ACLMessage
from pade.acl.aid import AID
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