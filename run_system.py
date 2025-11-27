import json
import time
import threading
import subprocess
import sys
import os
from pade.core.agent import Agent
from pade.acl.aid import AID
from pade.misc.utility import start_loop

from agents.distribution_agent import DistributionAgent
from agents.courier_agent import CourierAgent
from agents.monitor_agent import MonitorAgent


def load_data():
    with open("input_data.json", "r", encoding="utf-8") as f:
        return json.load(f)


def start_pade_system():
    """Запуск PADE системы"""
    print("🚀 Запуск PADE системы доставки...")

    data = load_data()
    couriers_data = data.get("couriers", [])
    orders_data = data.get("orders", [])

    print(f"📦 Заказов: {len(orders_data)}")
    print(f"🚚 Курьеров: {len(couriers_data)}")

    agents = []

    # Агент мониторинга
    monitor_agent = MonitorAgent(AID(name="monitor_agent"))
    agents.append(monitor_agent)

    # Агент распределения
    distribution_agent = DistributionAgent(
        AID(name="distribution_agent"),
        couriers_data,
        orders_data
    )
    agents.append(distribution_agent)

    # Агенты курьеров
    for courier_data in couriers_data:
        courier_agent = CourierAgent(
            AID(name=f"courier_{courier_data['id']}"),
            courier_data
        )
        agents.append(courier_agent)

    print("✅ Все агенты созданы!")

    # Запускаем PADE
    try:
        start_loop(agents)
    except KeyboardInterrupt:
        print("\n🛑 Система остановлена пользователем")


def start_web_gui():
    """Запуск Web GUI в отдельном процессе"""
    print("🌐 Запуск Web GUI на http://localhost:8001")

    # Запускаем web_gui.py как отдельный процесс
    try:
        subprocess.run([sys.executable, "web_gui.py"], check=True)
    except subprocess.CalledProcessError as e:
        print(f"❌ Ошибка запуска Web GUI: {e}")
    except KeyboardInterrupt:
        print("🌐 Web GUI остановлен")


def run_web_gui_in_thread():
    """Запуск Web GUI в отдельном потоке"""
    web_thread = threading.Thread(target=start_web_gui, daemon=True)
    web_thread.start()
    return web_thread


if __name__ == "__main__":
    print("=" * 50)
    print("🚚 СИСТЕМА ДОСТАВКИ КУРЬЕРОВ - PADE")
    print("=" * 50)

    # Запускаем Web GUI в фоновом режиме
    print("🔄 Запускаем Web GUI...")
    web_thread = run_web_gui_in_thread()

    # Ждем немного чтобы Web GUI успел запуститься
    print("⏳ Ожидаем запуск Web GUI (3 секунды)...")
    time.sleep(3)

    print("🎯 Запускаем PADE систему...")
    print("💡 Web GUI доступен по адресу: http://localhost:8001")
    print("⏹️  Для остановки нажмите Ctrl+C")
    print("-" * 50)

    # Запускаем PADE систему (это блокирующий вызов)
    start_pade_system()