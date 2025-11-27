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

app = FastAPI(title="Courier Delivery System")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

        couriers = {}
        for courier_data in data.get("couriers", []):
            courier_id = str(courier_data['id'])
            couriers[courier_id] = {
                "data": {
                    "id": courier_data['id'],
                    "name": courier_data['name'],
                    "transport_type": courier_data['transport_type'],
                    "max_capacity": courier_data['max_capacity']
                },
                "current_capacity": 0.0,
                "assigned_orders": [],
                "status": "available"
            }
            print(f"✅ WEB GUI: Загружен курьер: {courier_data['name']}")

        orders = {}
        for order_data in data.get("orders", []):
            order_id = str(order_data['id'])
            orders[order_id] = {
                "data": {
                    "id": order_data['id'],
                    "weight": order_data['weight'],
                    "description": order_data['description'],
                    "recipient": order_data.get('recipient', 'Не указан'),
                    "recipient_phone": order_data.get('recipient_phone', '')
                },
                "status": "pending",
                "assigned_courier": None
            }

        orders_count = len(data.get("orders", []))
        print(f"✅ WEB GUI: Курьеров: {len(couriers)}, Заказов: {orders_count}")
        return couriers, orders, orders_count

    except Exception as e:
        print(f"❌ Ошибка загрузки: {e}")
        # Данные по умолчанию
        couriers = {
            "1": {
                "data": {
                    "id": 1,
                    "name": "Иван Петров",
                    "transport_type": "car",
                    "max_capacity": 50.0
                },
                "current_capacity": 0.0,
                "assigned_orders": [],
                "status": "available"
            },
            "2": {
                "data": {
                    "id": 2,
                    "name": "Анна Сидорова",
                    "transport_type": "bicycle",
                    "max_capacity": 15.0
                },
                "current_capacity": 0.0,
                "assigned_orders": [],
                "status": "available"
            }
        }

        orders = {
            "101": {
                "data": {
                    "id": 101,
                    "weight": 5.0,
                    "description": "Срочный документ",
                    "recipient": "ООО 'Компания'",
                    "recipient_phone": "+79991230001"
                },
                "status": "pending",
                "assigned_courier": None
            },
            "102": {
                "data": {
                    "id": 102,
                    "weight": 3.0,
                    "description": "Посылка с одеждой",
                    "recipient": "Иванова Мария",
                    "recipient_phone": "+79991230002"
                },
                "status": "pending",
                "assigned_courier": None
            }
        }

        return couriers, orders, 2


class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        initial_couriers, initial_orders, total_orders = load_initial_data()

        self.system_state = {
            "logs": [
                {
                    "timestamp": time.time(),
                    "agent": "system",
                    "message": "🖥️ Система мониторинга запущена"
                }
            ],
            "statistics": {
                "total_orders": total_orders,
                "delivered_orders": 0,
                "assigned_orders": 0,
                "pending_orders": total_orders,
                "active_couriers": len(initial_couriers),
                "total_capacity": sum(courier["data"]["max_capacity"] for courier in initial_couriers.values()),
                "used_capacity": 0.0,
                "system_load": 0.0
            },
            "couriers": initial_couriers,
            "orders": initial_orders
        }
        print(f"✅ WEB GUI: Курьеров: {len(initial_couriers)}, Заказов: {total_orders}")

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

    def update_courier(self, courier_id: str, updates: Dict[str, Any]):
        if courier_id in self.system_state["couriers"]:
            self.system_state["couriers"][courier_id].update(updates)
        else:
            self.system_state["couriers"][courier_id] = updates

        asyncio.create_task(self.broadcast({
            "type": "courier_update",
            "courier_id": courier_id,
            "data": self.system_state["couriers"][courier_id]
        }))

    def update_order(self, order_id: str, updates: Dict[str, Any]):
        if order_id in self.system_state["orders"]:
            self.system_state["orders"][order_id].update(updates)
        else:
            self.system_state["orders"][order_id] = updates

        asyncio.create_task(self.broadcast({
            "type": "order_update",
            "order_id": order_id,
            "data": self.system_state["orders"][order_id]
        }))

    def update_statistics(self, new_stats: Dict[str, Any]):
        self.system_state["statistics"].update(new_stats)

        asyncio.create_task(self.broadcast({
            "type": "statistics_update",
            "statistics": self.system_state["statistics"]
        }))

    def send_orders_list(self):
        """Отправляет полный список заказов"""
        asyncio.create_task(self.broadcast({
            "type": "orders_list",
            "orders": self.system_state["orders"]
        }))


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


@app.post("/api/update_statistics")
async def update_statistics(request: Request):
    try:
        data = await request.json()
        manager.update_statistics(data)
        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


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

        print(f"✅ WEB GUI: Новый сценарий: {file.filename}")
        print(f"   Курьеров: {len(data.get('couriers', []))}")
        print(f"   Заказов: {len(data.get('orders', []))}")

        return JSONResponse({
            "status": "success",
            "message": f"Файл загружен! Курьеров: {len(data.get('couriers', []))}, Заказов: {len(data.get('orders', []))}",
            "requires_restart": True,
            "data": {
                "couriers_count": len(data.get('couriers', [])),
                "orders_count": len(data.get('orders', []))
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

        # Отправляем список заказов
        manager.send_orders_list()

        while True:
            data = await websocket.receive_text()
            try:
                command = json.loads(data)
                if command.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
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
            uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")
            break
        else:
            print(f"⚠️  Порт {port} занят")
    else:
        print("❌ Не удалось найти свободный порт")