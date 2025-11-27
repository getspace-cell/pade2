# Конфигурационные параметры системы
SERVER_HOST = "localhost"
SERVER_PORT = 8000
PADE_PORT = 8001

# Параметры распределения заказов
WORKDAY_START_TIME = "09:00"

# Типы транспорта и их грузоподъемность (кг)
TRANSPORT_CAPACITIES = {
    "foot": 10.0,
    "bicycle": 20.0,
    "car": 100.0,
    "motorcycle": 30.0
}

# Скорости транспорта (км/ч)
TRANSPORT_SPEEDS = {
    "foot": 5,
    "bicycle": 15,
    "car": 30,
    "motorcycle": 40
}

# Настройки Web GUI
WEB_HOST = "localhost"
WEB_PORT = 8000