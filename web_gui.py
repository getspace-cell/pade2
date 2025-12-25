# [file name]: web_gui.py
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, UploadFile, File, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import json
import time
from typing import List, Dict, Any
import asyncio
import shutil
from pathlib import Path
import subprocess
import os
import sys
import socket

app = FastAPI(title="Courier Delivery System - Balance Edition")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Создаем директории, если их нет
os.makedirs("static", exist_ok=True)
os.makedirs("templates", exist_ok=True)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


def is_port_free(port):
    """Проверяет свободен ли порт"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            s.bind(('localhost', port))
            return True
    except OSError:
        return False


def validate_input_data(data: dict) -> bool:
    required_keys = ['couriers', 'orders']
    if not all(key in data for key in required_keys):
        return False

    for courier in data.get('couriers', []):
        if not all(k in courier for k in ['id', 'name', 'transport_type', 'max_capacity']):
            return False

    for order in data.get('orders', []):
        if not all(k in order for k in ['id', 'weight', 'description']):
            return False

    return True


def load_initial_data():
    try:
        with open("input_data.json", "r", encoding="utf-8") as f:
            data = json.load(f)
        
        target_load_percent = data.get("target_load_percent")  # значение по умолчанию
        target_load_percentage = target_load_percent * 100


        couriers = {}
        for courier_data in data.get("couriers", []):
            courier_id = str(courier_data['id'])
            max_capacity = courier_data['max_capacity']
            couriers[courier_id] = {
                "data": {
                    "id": courier_data['id'],
                    "name": courier_data['name'],
                    "transport_type": courier_data['transport_type'],
                    "max_capacity": max_capacity
                },
                "current_capacity": 0.0,
                "assigned_orders": [],
                "status": "available",
                "message_count": 0,
                "location": "база",
                "utilization": 0.0,
                "is_overloaded": False,
                "helps_provided": 0,
                "problems_encountered": 0
            }
            print(f"✅ WEB GUI: Загружен курьер: {courier_data['name']} ({max_capacity}кг)")

        orders = {}
        for order_data in data.get("orders", []):
            order_id = str(order_data['id'])
            orders[order_id] = {
                "data": {
                    "id": order_data['id'],
                    "weight": order_data['weight'],
                    "description": order_data['description'],
                    "recipient": order_data.get('recipient', 'Не указан'),
                    "recipient_phone": order_data.get('recipient_phone', ''),
                    "priority": order_data.get('priority', 'normal')
                },
                "status": "pending",
                "assigned_courier": None,
                "created_time": time.time()
            }

        orders_count = len(data.get("orders", []))
        total_capacity = sum(c['max_capacity'] for c in data.get("couriers", []))

        print(f"✅ WEB GUI: Курьеров: {len(couriers)}, Заказов: {orders_count}")
        print(f"✅ WEB GUI: Общая грузоподъемность: {total_capacity}кг")

        return couriers, orders, orders_count, total_capacity, target_load_percent

    except Exception as e:
        print(f"❌ Ошибка загрузки: {e}")
        # Данные по умолчанию для балансировки
        return get_default_balanced_data()


def get_default_balanced_data():
    """Данные по умолчанию для тестирования балансировки"""
    couriers = {
        "1": {
            "data": {
                "id": 1,
                "name": "Иван Петров",
                "transport_type": "car",
                "max_capacity": 100.0
            },
            "current_capacity": 0.0,
            "assigned_orders": [],
            "status": "available",
            "message_count": 0,
            "location": "база",
            "utilization": 0.0,
            "is_overloaded": False,
            "helps_provided": 0,
            "problems_encountered": 0
        },
        "2": {
            "data": {
                "id": 2,
                "name": "Анна Сидорова",
                "transport_type": "bicycle",
                "max_capacity": 25.0
            },
            "current_capacity": 0.0,
            "assigned_orders": [],
            "status": "available",
            "message_count": 0,
            "location": "база",
            "utilization": 0.0,
            "is_overloaded": False,
            "helps_provided": 0,
            "problems_encountered": 0
        },
        "3": {
            "data": {
                "id": 3,
                "name": "Петр Иванов",
                "transport_type": "motorcycle",
                "max_capacity": 40.0
            },
            "current_capacity": 0.0,
            "assigned_orders": [],
            "status": "available",
            "message_count": 0,
            "location": "база",
            "utilization": 0.0,
            "is_overloaded": False,
            "helps_provided": 0,
            "problems_encountered": 0
        }
    }

    orders = {
        "101": {
            "data": {
                "id": 101,
                "weight": 60.0,
                "description": "ТЯЖЕЛЫЙ: Промышленное оборудование (тест балансировки)",
                "recipient": "Завод 'Металл'",
                "recipient_phone": "+79991230001",
                "priority": "high"
            },
            "status": "pending",
            "assigned_courier": None,
            "created_time": time.time()
        },
        "102": {
            "data": {
                "id": 102,
                "weight": 35.0,
                "description": "Офисная мебель",
                "recipient": "ООО 'ОфисПлюс'",
                "recipient_phone": "+79991230002",
                "priority": "normal"
            },
            "status": "pending",
            "assigned_courier": None,
            "created_time": time.time()
        },
        "103": {
            "data": {
                "id": 103,
                "weight": 15.0,
                "description": "Документы в банк",
                "recipient": "Банк 'Финансы'",
                "recipient_phone": "+79991230003",
                "priority": "high"
            },
            "status": "pending",
            "assigned_courier": None,
            "created_time": time.time()
        }
    }

    total_capacity = sum(c["data"]["max_capacity"] for c in couriers.values())
    return couriers, orders, 3, total_capacity


class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        initial_couriers, initial_orders, total_orders, total_capacity, target_load_percent = load_initial_data()
        self.system_state = {
            "logs": [
                {
                    "timestamp": time.time(),
                    "agent": "system",
                    "message": "🖥️ Система мониторинга запущена (режим балансировки нагрузки)"
                },
                {
                    "timestamp": time.time(),
                    "agent": "system",
                    "message": "🎯 Целевая загрузка системы: 80%"
                },
                {
                    "timestamp": time.time(),
                    "agent": "system",
                    "message": "🔄 Режим перераспределения заказов: АКТИВЕН"
                }
            ],
            "statistics": {
                "total_orders": total_orders,
                "delivered_orders": 0,
                "assigned_orders": 0,
                "pending_orders": total_orders,
                "active_couriers": len(initial_couriers),
                "total_capacity": total_capacity,
                "used_capacity": 0.0,
                "system_load": 0.0,
                "messages_exchanged": 0,
                "target_load": 80.0,
                "load_imbalance": 0.0,
                "balance_efficiency": 0.0,
                "transfers_completed": 0,
                "help_requests": 0,
                "balance_alerts": 0
            },
            "couriers": initial_couriers,
            "orders": initial_orders,
            "communications": [],
            "balance_history": []  # История изменений баланса
        }

        self.target_load_percent = target_load_percent


        print(f"✅ WEB GUI: Инициализирована система балансировки")
        print(f"   📊 Курьеров: {len(initial_couriers)}, Заказов: {total_orders}")
        print(f"   🎯 Целевая загрузка: 80%")

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: Dict[str, Any]):
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                disconnected.append(connection)

        for connection in disconnected:
            self.disconnect(connection)

    def add_log(self, message: str, agent: str = "system"):
        log_entry = {
            "timestamp": time.time(),
            "agent": agent,
            "message": message
        }
        self.system_state["logs"].append(log_entry)

        if len(self.system_state["logs"]) > 100:
            self.system_state["logs"] = self.system_state["logs"][-100:]

        asyncio.create_task(self.broadcast({
            "type": "log_update",
            "log": log_entry
        }))

    def add_communication(self, message: Dict[str, Any]):
        """Добавляет сообщение в историю общения"""
        # ИЗМЕНЕНИЕ: Определяем отправителя и получателя для передачи заказов
        sender = message.get("sender", "unknown")
        receiver = message.get("receiver", "unknown")
        msg_type = message.get("type", "unknown")
        content = message.get("content", {})

        # ИЗМЕНЕНИЕ: Для сообщений о передаче от координатора меняем отправителя/получателя
        if msg_type in ["transfer_proposal_incoming", "transfer_proposal_outgoing"]:
            is_direct = content.get("is_direct", False)

            if is_direct:
                # Если это прямое сообщение между курьерами
                if "from_courier" in content:
                    sender = content["from_courier"]
                elif "from_courier_id" in content:
                    sender = f"courier_{content['from_courier_id']}"

                if "to_courier" in content:
                    receiver = content["to_courier"]
                elif "to_courier_id" in content:
                    receiver = f"courier_{content['to_courier_id']}"

        # Форматируем сообщение для отображения
        formatted_msg = {
            "id": len(self.system_state["communications"]) + 1,
            "timestamp": time.time(),
            "time_str": time.strftime("%H:%M:%S", time.localtime()),
            "sender": sender,
            "receiver": receiver,
            "type": msg_type,
            "content": content,
            "direction": message.get("direction", "unknown")
        }

        self.system_state["communications"].append(formatted_msg)

        # Ограничиваем историю
        if len(self.system_state["communications"]) > 200:
            self.system_state["communications"] = self.system_state["communications"][-200:]

        # Увеличиваем счетчик сообщений в статистике
        self.system_state["statistics"]["messages_exchanged"] += 1

        # Считаем специальные типы сообщений
        msg_type = message.get("type", "")
        if "transfer" in msg_type or "offer" in msg_type:
            self.system_state["statistics"]["transfers_completed"] += 1
        elif "help" in msg_type:
            self.system_state["statistics"]["help_requests"] += 1
        elif "balance" in msg_type or "overload" in msg_type:
            self.system_state["statistics"]["balance_alerts"] += 1

        # Рассылаем обновление статистики всем клиентам
        self.update_balance_statistics()

        # Рассылаем обновление сообщения
        asyncio.create_task(self.broadcast({
            "type": "communication_update",
            "communication": formatted_msg,
            "total_messages": self.system_state["statistics"]["messages_exchanged"]
        }))

        # ИЗМЕНЕНИЕ: Выводим логи с учетом изменений
        if msg_type in ["transfer_proposal_incoming", "transfer_proposal_outgoing"]:
            from_name = content.get("from_courier_name", "Коллега")
            to_name = content.get("to_courier_name", "Коллега")
            order_id = content.get("order", {}).get("id", "N/A")

            if msg_type == "transfer_proposal_incoming":
                print(f"🔄 Сообщение от {from_name} к {to_name}: передача заказа #{order_id}")
            else:
                print(f"🔄 Сообщение от {from_name} к {to_name}: предложение передачи заказа #{order_id}")
        else:
            print(f"💬 Сообщение от {formatted_msg['sender']} к {formatted_msg['receiver']}: {formatted_msg['type']}")

    def update_courier(self, courier_id: str, updates: Dict[str, Any]):
        """Обновляет данные курьера"""
        if courier_id in self.system_state["couriers"]:
            # Обновляем утилизацию
            if "current_capacity" in updates and "data" in self.system_state["couriers"][courier_id]:
                current_capacity = updates.get("current_capacity", 0)
                max_capacity = self.system_state["couriers"][courier_id]["data"]["max_capacity"]
                utilization = (current_capacity / max_capacity * 100) if max_capacity > 0 else 0
                updates["utilization"] = utilization
                updates["is_overloaded"] = utilization > 80

            self.system_state["couriers"][courier_id].update(updates)
        else:
            # Добавляем нового курьера
            self.system_state["couriers"][courier_id] = updates

        # Обновляем статистику системы
        self.update_balance_statistics()

        # Рассылаем обновление
        asyncio.create_task(self.broadcast({
            "type": "courier_update",
            "courier_id": courier_id,
            "data": self.system_state["couriers"][courier_id]
        }))

    def update_order(self, order_id: str, updates: Dict[str, Any]):
        """Обновляет данные заказа"""
        if order_id in self.system_state["orders"]:
            self.system_state["orders"][order_id].update(updates)

            # Если заказ доставлен, обновляем статистику
            if updates.get("status") == "delivered":
                self.system_state["statistics"]["delivered_orders"] += 1
                self.system_state["statistics"]["assigned_orders"] = max(
                    0, self.system_state["statistics"]["assigned_orders"] - 1
                )
                self.update_balance_statistics()
        else:
            self.system_state["orders"][order_id] = updates

        asyncio.create_task(self.broadcast({
            "type": "order_update",
            "order_id": order_id,
            "data": self.system_state["orders"][order_id]
        }))

    def update_statistics(self, new_stats: Dict[str, Any]):
        """Обновляет статистику"""
        self.system_state["statistics"].update(new_stats)
        self.update_balance_statistics()

    def update_balance_statistics(self):
        """Пересчитывает статистику балансировки"""
        stats = self.system_state["statistics"]
        couriers = self.system_state["couriers"]

        # Пересчитываем загрузку системы
        total_capacity = stats["total_capacity"]
        used_capacity = sum(c.get("current_capacity", 0) for c in couriers.values())
        system_load = (used_capacity / total_capacity * 100) if total_capacity > 0 else 0

        stats["used_capacity"] = used_capacity
        stats["system_load"] = system_load

        # Пересчитываем количество активных курьеров и заказов
        stats["active_couriers"] = len([c for c in couriers.values()
                                        if c.get("status") in ["delivering", "collecting"]])
        stats["pending_orders"] = len([o for o in self.system_state["orders"].values()
                                       if o.get("status") == "pending"])
        stats["assigned_orders"] = len([o for o in self.system_state["orders"].values()
                                        if o.get("status") == "assigned"])

        # Рассчитываем дисбаланс (стандартное отклонение утилизации)
        utilizations = [c.get("utilization", 0) for c in couriers.values()]
        if utilizations:
            mean_util = sum(utilizations) / len(utilizations)
            variance = sum((u - mean_util) ** 2 for u in utilizations) / len(utilizations)
            stats["load_imbalance"] = variance ** 0.5
        else:
            stats["load_imbalance"] = 0

        # Рассчитываем эффективность балансировки
        target_load = stats.get("target_load", 80)
        efficiency = 100 - abs(system_load - target_load)
        stats["balance_efficiency"] = max(0, min(efficiency, 100))

        # Добавляем запись в историю баланса
        balance_record = {
            "timestamp": time.time(),
            "system_load": system_load,
            "imbalance": stats["load_imbalance"],
            "efficiency": stats["balance_efficiency"]
        }
        self.system_state["balance_history"].append(balance_record)

        if len(self.system_state["balance_history"]) > 50:
            self.system_state["balance_history"] = self.system_state["balance_history"][-50:]

        # Рассылаем обновление
        asyncio.create_task(self.broadcast({
            "type": "statistics_update",
            "statistics": stats
        }))

    def send_communications_list(self):
        """Отправляет список сообщений"""
        asyncio.create_task(self.broadcast({
            "type": "communications_list",
            "communications": self.system_state["communications"][-50:],
            "total_messages": self.system_state["statistics"]["messages_exchanged"]
        }))

    def send_balance_report(self):
        """Отправляет отчет о балансировке"""
        stats = self.system_state["statistics"]
        couriers = self.system_state["couriers"]

        # Анализируем загрузку курьеров
        overloaded = [c for c in couriers.values() if c.get("is_overloaded", False)]
        underloaded = [c for c in couriers.values()
                       if c.get("utilization", 0) < 30 and c.get("current_capacity", 0) > 0]

        report = {
            "type": "balance_report",
            "timestamp": time.time(),
            "system_load": stats["system_load"],
            "target_load": stats.get("target_load", 80),
            "imbalance": stats["load_imbalance"],
            "efficiency": stats["balance_efficiency"],
            "overloaded_couriers": len(overloaded),
            "underloaded_couriers": len(underloaded),
            "transfers_completed": stats["transfers_completed"],
            "status": "good" if stats["load_imbalance"] < 15 else
            "warning" if stats["load_imbalance"] < 30 else
            "critical"
        }

        asyncio.create_task(self.broadcast(report))


manager = ConnectionManager()


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/api/log")
async def add_log(request: Request):
    try:
        data = await request.json()
        manager.add_log(data.get("message", ""), data.get("agent", "system"))
        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.post("/api/log_communication")
async def log_communication(request: Request):
    try:
        data = await request.json()
        manager.add_communication(data)
        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.post("/api/update_courier/{courier_id}")
async def update_courier(courier_id: str, request: Request):
    try:
        data = await request.json()
        manager.update_courier(courier_id, data)
        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.post("/api/update_order/{order_id}")
async def update_order(order_id: str, request: Request):
    try:
        data = await request.json()
        manager.update_order(order_id, data)
        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/target_load")
async def get_target_load():
    """Возвращает целевую загрузку из системы"""
    return {
        "status": "success",
        "target_load_percent": manager.target_load_percent,
        "target_load_percentage": manager.target_load_percent * 100
    }
# В коде запуска системы добавьте получение target_load_percent из веб-интерфейса
@app.post("/api/start-system")
async def start_system():
    try:
        # Получаем целевую загрузку из менеджера веб-интерфейса
        target_load_percent = manager.target_load_percent
        
        # Запускаем систему агентов с передачей target_load_percent
        # Пример кода запуска (зависит от вашей реализации):
        # agent_system.start(target_load_percent=target_load_percent)
        
        return {"status": "success", "target_load_percent": target_load_percent}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/update_statistics")
async def update_statistics(request: Request):
    try:
        data = await request.json()
        manager.update_statistics(data)
        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/api/balance_report")
async def get_balance_report():
    """Возвращает отчет о балансировке"""
    manager.send_balance_report()
    return {"status": "success", "message": "Balance report sent"}


@app.post("/api/upload-json")
async def upload_json_file(file: UploadFile = File(...)):
    if not file.filename.endswith('.json'):
        raise HTTPException(status_code=400, detail="Только JSON файлы")

    try:
        content = await file.read()
        data = json.loads(content)

        if not validate_input_data(data):
            raise HTTPException(status_code=400, detail="Неверный формат")

        backup_file = "input_data_backup.json"
        original_file = "input_data.json"

        if Path(original_file).exists():
            shutil.copy(original_file, backup_file)

        with open(original_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        couriers_count = len(data.get('couriers', []))
        orders_count = len(data.get('orders', []))
        total_capacity = sum(c.get('max_capacity', 0) for c in data.get('couriers', []))

        print(f"✅ WEB GUI: Загружен новый сценарий: {file.filename}")
        print(f"   📊 Курьеров: {couriers_count}")
        print(f"   📦 Заказов: {orders_count}")
        print(f"   🏋️  Общая грузоподъемность: {total_capacity}кг")

        # Создаем системное сообщение о загрузке сценария
        manager.add_log(f"📂 Загружен сценарий: {file.filename}", "system")
        manager.add_log(f"📊 Курьеров: {couriers_count}, Заказов: {orders_count}", "system")
        manager.add_log(f"🏋️  Общая грузоподъемность: {total_capacity}кг", "system")
        manager.add_log("🔄 Для применения сценария перезагрузите систему", "system")

        return JSONResponse({
            "status": "success",
            "message": f"Файл загружен! Курьеров: {couriers_count}, Заказов: {orders_count}",
            "requires_restart": True,
            "data": {
                "couriers_count": couriers_count,
                "orders_count": orders_count,
                "total_capacity": total_capacity
            }
        })

    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Неверный JSON")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка: {str(e)}")


@app.post("/api/restart-system")
async def restart_system():
    """Перезапуск системы"""
    try:
        print("🔄 WEB GUI: Запускаем перезапуск системы...")
        manager.add_log("🔄 Система перезапускается...", "system")

        # Немедленный ответ клиенту
        response = {"status": "success", "message": "Система перезапускается..."}

        # Запускаем перезапуск в фоне
        subprocess.Popen([sys.executable, "restart_system.py"])

        return response

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return {"status": "error", "message": f"Ошибка: {str(e)}"}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        # Отправляем текущее состояние
        await websocket.send_json({
            "type": "initial_state",
            "data": manager.system_state
        })

        # Отправляем историю общения
        manager.send_communications_list()

        # Отправляем отчет о балансировке
        manager.send_balance_report()

        while True:
            data = await websocket.receive_text()
            try:
                command = json.loads(data)
                if command.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
                elif command.get("type") == "get_communications":
                    # Отправляем историю сообщений по запросу
                    manager.send_communications_list()
                elif command.get("type") == "get_balance_report":
                    # Отправляем отчет о балансировке
                    manager.send_balance_report()
            except:
                pass

    except WebSocketDisconnect:
        manager.disconnect(websocket)


if __name__ == "__main__":
    # Пробуем разные порты
    ports = [8001, 8002, 8003, 8004]
    for port in ports:
        if is_port_free(port):
            print(f"🌐 Запускаем Web GUI на порту {port}")
            print(f"🎯 Режим: Балансировка нагрузки")
            print(f"🔄 Перераспределение заказов: АКТИВНО")
            print(f"📊 Статистика балансировки: ВКЛЮЧЕНО")
            uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")
            break
        else:
            print(f"⚠️  Порт {port} занят")
    else:
        print("❌ Не удалось найти свободный порт")