# [file name]: models.py
from enum import Enum
from typing import List, Dict, Any
import time
from dataclasses import dataclass
from datetime import datetime


class TransportType(str, Enum):
    CAR = "car"
    BICYCLE = "bicycle"
    MOTORCYCLE = "motorcycle"
    FOOT = "foot"


class District(str, Enum):
    KALININSKY = "калининский"
    SOVETSKY = "советский"
    LENINSKY = "ленинский"
    KIROVSKY = "кировский"


class OrderStatus(str, Enum):
    PENDING = "pending"
    ASSIGNED = "assigned"
    DELIVERING = "delivering"
    DELIVERED = "delivered"


class CourierStatus(str, Enum):
    AVAILABLE = "available"
    COLLECTING = "collecting"
    DELIVERING = "delivering"
    IN_TRANSIT = "in_transit"


class MessageType(str, Enum):
    ORDER_ASSIGNMENT = "order_assignment"
    ORDER_ACCEPTED = "order_accepted"
    ORDER_DELIVERED = "order_delivered"
    HELP_REQUEST = "help_request"
    HELP_OFFER = "help_offer"
    RESOURCE_SHARE = "resource_share"
    COORDINATION = "coordination"
    INFO_REQUEST = "info_request"
    INFO_RESPONSE = "info_response"


@dataclass
class Message:
    sender_id: str
    receiver_id: str
    message_type: MessageType
    content: Dict[str, Any]
    timestamp: float = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()

    def to_dict(self):
        return {
            "sender_id": self.sender_id,
            "receiver_id": self.receiver_id,
            "message_type": self.message_type.value,
            "content": self.content,
            "timestamp": self.timestamp,
            "time_str": datetime.fromtimestamp(self.timestamp).strftime("%H:%M:%S")
        }


class Courier:
    def __init__(self, data: Dict[str, Any]):
        self.id = data["id"]
        self.name = data["name"]
        self.location = data.get("location", "base")
        self.transport_type = data["transport_type"]
        self.max_capacity = data["max_capacity"]
        self.current_capacity = 0.0
        self.current_orders = []
        self.status = CourierStatus.AVAILABLE
        self.contact = data.get("contact", "")
        self.speed = data.get("speed", 10)
        self.message_history = []
        self.district = data.get("district", "калининский")  # НОВОЕ ПОЛЕ


class Order:
    def __init__(self, data: Dict[str, Any]):
        self.id = data["id"]
        self.destination = data.get("destination", "Не указан")
        self.weight = data["weight"]
        self.description = data["description"]
        self.recipient = data.get("recipient", "Не указан")
        self.recipient_phone = data.get("recipient_phone", "")
        self.status = OrderStatus.PENDING
        self.assigned_courier = None
        self.created_time = time.time()
        self.assigned_time = None
        self.delivered_time = None
        self.priority = data.get("priority", "normal")
        self.district = data.get("district", "калининский")  # НОВОЕ ПОЛЕ


class CommunicationLog:
    def __init__(self):
        self.messages = []

    def add_message(self, message: Message):
        self.messages.append(message)
        if len(self.messages) > 100:
            self.messages = self.messages[-100:]

    def get_messages(self, limit: int = 50):
        return self.messages[-limit:] if self.messages else []


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
            "used_capacity": 0,
            "messages_exchanged": 0
        }
        self.communication_log = CommunicationLog()