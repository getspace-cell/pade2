import json
from agents.base_agent import BaseAgent
from pade.pade.behaviours.protocols import FipaRequestProtocol


class MonitorAgent(BaseAgent):
    def __init__(self, aid):
        super().__init__(aid)
        self.behaviours.append(MonitorBehaviour(self))

    def on_start(self):
        self.log("📊 Агент мониторинга запущен")


class MonitorBehaviour(FipaRequestProtocol):
    def __init__(self, agent):
        super().__init__(agent, is_initiator=False)
        self.agent = agent

    def handle_request(self, message):
        """Обрабатываем входящие сообщения"""
        try:
            content = json.loads(message.content)
            self.agent.log(f"📊 Мониторинг: {content.get('type')} от {message.sender.name}")
        except Exception as e:
            self.agent.log(f"❌ Ошибка мониторинга: {e}")