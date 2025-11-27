from enum import Enum
from typing import List, Dict, Any
import time

class TransportType(str, Enum):
    CAR = "car"
    BICYCLE = "bicycle"
    MOTORCYCLE = "motorcycle"
    FOOT = "foot"

class OrderStatus(str, Enum):
    PENDING = "pending"
    ASSIGNED = "assigned"
    DELIVERED = "delivered"

class CourierStatus(str, Enum):
    AVAILABLE = "available"
    COLLECTING = "collecting"
    DELIVERING = "delivering"

class Courier:
    def __init__(self, data: Dict[str, Any]):
        self.id = data["id"]
        self.name = data["name"]
        self.location = data["location"]
        self.transport_type = data["transport_type"]
        self.max_capacity = data["max_capacity"]
        self.current_capacity = 0.0
        self.current_orders = []
        self.status = CourierStatus.AVAILABLE
        self.contact = data.get("contact", "")
        self.speed = None

class Order:
    def __init__(self, data: Dict[str, Any]):
        self.id = data["id"]
        self.destination = data["destination"]
        self.weight = data["weight"]
        self.description = data["description"]
        self.recipient = data["recipient"]
        self.recipient_phone = data["recipient_phone"]
        self.status = OrderStatus.PENDING
        self.assigned_courier = None
        self.created_time = time.time()
        self.assigned_time = None
        self.delivered_time = None

class SystemState:
    def __init__(self):
        self.couriers = {}
        self.orders = {}
        self.assignments = []
        self.statistics = {
            "total_orders": 0,
            "delivered_orders": 0,
            "assigned_orders": 0,
            "pending_orders": 0,
            "active_couriers": 0,
            "total_capacity": 0,
            "used_capacity": 0
        }