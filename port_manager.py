import socket
import random


class PortManager:
    def __init__(self):
        self.used_ports = set()
        self.base_port = 30000

    def find_free_port(self):
        """Находит свободный порт"""
        # Пробуем случайные порты в диапазоне
        for _ in range(100):
            port = random.randint(30000, 60000)
            if port not in self.used_ports and self.is_port_free(port):
                self.used_ports.add(port)
                return port

        # Если не нашли случайный, ищем последовательно
        for port in range(self.base_port, 60000):
            if port not in self.used_ports and self.is_port_free(port):
                self.used_ports.add(port)
                return port

        raise Exception("Не удалось найти свободный порт")

    def is_port_free(self, port):
        """Проверяет, свободен ли порт"""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(1)
                s.bind(('localhost', port))
                return True
        except (OSError, socket.timeout):
            return False

    def release_port(self, port):
        """Освобождает порт"""
        if port in self.used_ports:
            self.used_ports.remove(port)


port_manager = PortManager()