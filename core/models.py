# models.py
# Definições de dataclasses e modelos de domínio

from dataclasses import dataclass
from typing import Optional

@dataclass
class User:
    id: int
    username: str
    password_hash: str
    role: str

@dataclass
class Customer:
    id: int
    name: str
    phone: Optional[str]
    address: Optional[str]
    birthday: Optional[str]

@dataclass
class Product:
    id: int
    name: str
    description: Optional[str]
    size: Optional[str]
    price: float
    stock: int
    min_stock: int

@dataclass
class Order:
    id: int
    customer_id: int
    product_id: int
    quantity: int
    delivery_date: str
    total: float
    status: str
    notes: Optional[str]
    created_at: str
