from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from fastapi import Request
import json
import asyncio
from typing import List, Dict, Any
import uvicorn

app = FastAPI(title="Courier Delivery System - PADE")

# Монтируем статические файлы
app.mount("/static", StaticFiles(directory="project/static"), name="static")
templates = Jinja2Templates(directory="project/templates")


class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: Dict[str, Any]):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                self.disconnect(connection)


manager = ConnectionManager()

# Глобальное состояние для Web GUI
system_state = {
    "logs": [],
    "statistics": {},
    "couriers": {},
    "orders": {}
}


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        # Отправляем текущее состояние при подключении
        await websocket.send_json({
            "type": "initial_state",
            "data": system_state
        })

        while True:
            data = await websocket.receive_text()
            # Обработка команд от клиента
            try:
                command = json.loads(data)
                if command.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
            except:
                pass

    except WebSocketDisconnect:
        manager.disconnect(websocket)


def update_system_state(new_state: Dict[str, Any]):
    """Обновление состояния системы из агентов"""
    global system_state
    system_state.update(new_state)

    # Рассылаем обновления всем подключенным клиентам
    asyncio.create_task(manager.broadcast({
        "type": "state_update",
        "data": new_state
    }))


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)