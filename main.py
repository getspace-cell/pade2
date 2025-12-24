import json
import time
from pade.pade.core.agent import Agent
from pade.pade.acl.aid import AID
from pade.pade.misc.utility import start_loop
import threading
import subprocess
import sys
import os
import atexit
import signal
import socket

from agents.coordinator_agent import CoordinatorAgent
from agents.courier_agent import CourierAgent
from agents.monitor_agent import MonitorAgent
from port_manager import port_manager

agents_list = []
is_shutting_down = False


def kill_process_on_port(port):
    """Принудительно освобождает порт"""
    try:
        if os.name == 'nt':  # Windows
            result = subprocess.run(
                ['netstat', '-ano'],
                capture_output=True, text=True
            )
            lines = result.stdout.split('\n')
            for line in lines:
                if f':{port}' in line and 'LISTENING' in line:
                    parts = line.split()
                    if len(parts) >= 5:
                        pid = parts[-1]
                        subprocess.run(['taskkill', '/F', '/PID', pid],
                                       capture_output=True)
                        print(f"🔴 Освобожден порт {port} (PID: {pid})")
        else:  # Unix/Linux
            result = subprocess.run(
                ['lsof', '-ti', f':{port}'],
                capture_output=True, text=True
            )
            if result.stdout.strip():
                pids = result.stdout.strip().split('\n')
                for pid in pids:
                    subprocess.run(['kill', '-9', pid], capture_output=True)
                    print(f"🔴 Освобожден порт {port} (PID: {pid})")
    except:
        pass


def signal_handler(signum, frame):
    """Обработчик сигналов"""
    global is_shutting_down
    if is_shutting_down:
        return

    is_shutting_down = True
    print(f"📞 Получен сигнал завершения")

    # Освобождаем порты
    for agent in agents_list:
        try:
            if hasattr(agent, 'aid') and hasattr(agent.aid, 'port'):
                port = agent.aid.port
                port_manager.release_port(port)
                kill_process_on_port(port)  # Принудительно освобождаем порт
        except:
            pass

    print("🧹 Завершаем работу...")
    os._exit(0)


def cleanup():
    """Функция очистки"""
    if is_shutting_down:
        print("🧹 Очистка ресурсов...")


def load_data():
    """Загрузка данных из JSON файла"""
    try:
        with open("input_data.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ Ошибка загрузки: {e}")
        return get_default_data()


def get_default_data():
    """Данные по умолчанию"""
    return {
        "couriers": [
            {
                "id": 1,
                "name": "Иван Петров",
                "transport_type": "car",
                "max_capacity": 50.0
            },
            {
                "id": 2,
                "name": "Анна Сидорова",
                "transport_type": "bicycle",
                "max_capacity": 15.0
            }
        ],
        "orders": [
            {"id": 101, "weight": 5.0, "description": "Срочный документ"},
            {"id": 102, "weight": 3.0, "description": "Посылка с одеждой"}
        ]
    }


def run_gui():
    """Запуск GUI сервера"""
    try:
        import uvicorn
        from web_gui import app

        # Принудительно освобождаем порты перед запуском
        for port in [8001, 8002, 8003, 8004]:
            kill_process_on_port(port)

        # Пробуем разные порты для GUI
        ports = [8001, 8002, 8003, 8004]
        for port in ports:
            try:
                # Проверяем свободен ли порт
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1)
                result = sock.connect_ex(('localhost', port))
                sock.close()

                if result != 0:  # Порт свободен
                    print(f"🌐 Запускаем Web GUI на порту {port}")
                    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")
                    break
                else:
                    print(f"⚠️  Порт {port} занят, освобождаем...")
                    kill_process_on_port(port)
                    time.sleep(1)

                    # Пробуем еще раз после освобождения
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(1)
                    result = sock.connect_ex(('localhost', port))
                    sock.close()

                    if result != 0:
                        print(f"🌐 Запускаем Web GUI на порту {port} (после освобождения)")
                        uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")
                        break
                    else:
                        print(f"❌ Не удалось освободить порт {port}")

            except OSError as e:
                print(f"⚠️  Ошибка порта {port}: {e}")
                continue
        else:
            print("❌ Не удалось запустить Web GUI")

    except Exception as e:
        print(f"❌ Ошибка GUI: {e}")


def create_agent_with_port(agent_class, name, *args):
    """Создает агента со свободным портом"""
    max_attempts = 10
    for attempt in range(max_attempts):
        try:
            port = port_manager.find_free_port()

            # Дополнительная проверка порта
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex(('localhost', port))
            sock.close()

            if result != 0:  # Порт действительно свободен
                aid = AID(name=name, addresses=[f"http://localhost:{port}"])
                agent = agent_class(aid, *args)
                agent.aid.port = port
                return agent
            else:
                print(f"⚠️  Порт {port} занят, пробуем другой...")
                kill_process_on_port(port)
                port_manager.release_port(port)
                continue

        except Exception as e:
            print(f"⚠️  Ошибка при создании агента: {e}")
            continue

    raise Exception(f"Не удалось найти свободный порт после {max_attempts} попыток")


def run_pade():
    """Запуск PADE системы"""
    global agents_list

    print("🎯 Запускаем систему координации доставки...")

    data = load_data()
    couriers_data = data.get("couriers", [])
    orders_data = data.get("orders", [])

    print(f"📦 Заказов: {len(orders_data)}")
    print(f"🚚 Курьеров: {len(couriers_data)}")

    # Выводим информацию
    for courier in couriers_data:
        print(f"   🚗 {courier['name']} ({courier['transport_type']}): {courier['max_capacity']}кг")

    for order in orders_data:
        print(f"   📦 Заказ {order['id']}: {order['weight']}кг - {order['description']}")

    agents_list = []

    try:
        # Создаем курьеров
        for courier_data in couriers_data:
            courier_agent = create_agent_with_port(
                CourierAgent,
                f"courier_{courier_data['id']}",
                courier_data
            )
            agents_list.append(courier_agent)
            print(f"✅ Создан курьер: {courier_data['name']} (порт: {courier_agent.aid.port})")

        # Агент координации (заменяем distribution_agent)
        coordinator_agent = create_agent_with_port(
            CoordinatorAgent,
            "coordinator_agent",
            couriers_data,
            orders_data
        )
        agents_list.append(coordinator_agent)
        print(f"✅ Создан агент координации (порт: {coordinator_agent.aid.port})")

        # Агент мониторинга
        monitor_agent = create_agent_with_port(
            MonitorAgent,
            "monitor_agent"
        )
        agents_list.append(monitor_agent)
        print(f"✅ Создан агент мониторинга (порт: {monitor_agent.aid.port})")

        print(f"✅ Всего агентов: {len(agents_list)}")
        print("⏳ Запускаем систему координации...")

        # Запускаем PADE
        start_loop(agents_list)

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        # Освобождаем порты при ошибке
        for agent in agents_list:
            if hasattr(agent, 'aid') and hasattr(agent.aid, 'port'):
                port = agent.aid.port
                port_manager.release_port(port)
                kill_process_on_port(port)
        raise


def main():
    """Главная функция"""
    # Регистрируем обработчики
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    atexit.register(cleanup)

    print("=" * 50)
    print("🚚 СИСТЕМА КООРДИНАЦИИ ДОСТАВКИ КУРЬЕРОВ")
    print("=" * 50)
    print(f"🆔 PID: {os.getpid()}")

    print("🔄 Запускаем Web GUI...")

    # Запускаем GUI в отдельном потоке
    gui_thread = threading.Thread(target=run_gui, daemon=True)
    gui_thread.start()

    print("⏳ Ожидаем запуск GUI (5 секунд)...")
    time.sleep(5)

    print("🎯 Запускаем систему координации...")
    run_pade()


if __name__ == "__main__":
    main()