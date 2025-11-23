from pydantic import BaseModel, EmailStr
from typing import Optional, List, Dict, Any
from datetime import datetime


# Driver Models
class DriverBase(BaseModel):
    name: str
    phone: Optional[str] = None
    email: Optional[str] = None


class DriverCreate(DriverBase):
    access_code: Optional[str] = None


class DriverUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    status: Optional[str] = None
    current_location_lat: Optional[float] = None
    current_location_lng: Optional[float] = None
    access_code: Optional[str] = None


class Driver(DriverBase):
    id: int
    status: str
    current_location_lat: Optional[float] = None
    current_location_lng: Optional[float] = None
    access_code: Optional[str] = None
    last_check_in_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


# Depot Models
class DepotBase(BaseModel):
    name: str
    address: str


class DepotCreate(DepotBase):
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class Depot(DepotBase):
    id: int
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    created_at: datetime

    class Config:
        from_attributes = True


# Parking Location Models
class ParkingLocationBase(BaseModel):
    name: Optional[str] = None
    address: str
    notes: Optional[str] = None


class ParkingLocationCreate(ParkingLocationBase):
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class ParkingLocation(ParkingLocationBase):
    id: int
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    created_at: datetime

    class Config:
        from_attributes = True


# Order Models
class OrderBase(BaseModel):
    delivery_address: str
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    customer_email: Optional[str] = None
    description: Optional[str] = None


class OrderCreate(OrderBase):
    order_number: Optional[str] = None
    items: Optional[List[Dict[str, Any]]] = None
    delivery_time_window_start: Optional[datetime] = None
    delivery_time_window_end: Optional[datetime] = None
    priority: Optional[str] = None  # Will be auto-set based on time window
    source: Optional[str] = None
    raw_text: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    assigned_driver_id: Optional[int] = None
    driver_status: Optional[str] = None
    driver_notes: Optional[str] = None
    failure_reason: Optional[str] = None
    driver_status_updated_at: Optional[datetime] = None
    driver_gps_lat: Optional[float] = None
    driver_gps_lng: Optional[float] = None
    delivered_at: Optional[datetime] = None
    failed_at: Optional[datetime] = None
    proof_photo_path: Optional[str] = None
    proof_signature_path: Optional[str] = None
    proof_metadata: Optional[Dict[str, Any]] = None
    proof_captured_at: Optional[datetime] = None


class OrderUpdate(BaseModel):
    delivery_address: Optional[str] = None
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    customer_email: Optional[str] = None
    description: Optional[str] = None
    items: Optional[List[Dict[str, Any]]] = None
    delivery_time_window_start: Optional[datetime] = None
    delivery_time_window_end: Optional[datetime] = None
    priority: Optional[str] = None
    status: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    assigned_driver_id: Optional[int] = None
    driver_status: Optional[str] = None
    driver_notes: Optional[str] = None
    failure_reason: Optional[str] = None
    driver_status_updated_at: Optional[datetime] = None
    driver_gps_lat: Optional[float] = None
    driver_gps_lng: Optional[float] = None
    delivered_at: Optional[datetime] = None
    failed_at: Optional[datetime] = None
    proof_photo_path: Optional[str] = None
    proof_signature_path: Optional[str] = None
    proof_metadata: Optional[Dict[str, Any]] = None
    proof_captured_at: Optional[datetime] = None


class Order(OrderBase):
    id: int
    order_number: Optional[str] = None
    items: Optional[List[Dict[str, Any]]] = None
    delivery_time_window_start: Optional[datetime] = None
    delivery_time_window_end: Optional[datetime] = None
    priority: str
    status: str
    source: Optional[str] = None
    raw_text: Optional[str] = None
    validation_errors: Optional[List[str]] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    assigned_driver_id: Optional[int] = None
    driver_status: Optional[str] = None
    driver_notes: Optional[str] = None
    failure_reason: Optional[str] = None
    driver_status_updated_at: Optional[datetime] = None
    driver_gps_lat: Optional[float] = None
    driver_gps_lng: Optional[float] = None
    delivered_at: Optional[datetime] = None
    failed_at: Optional[datetime] = None
    proof_photo_path: Optional[str] = None
    proof_signature_path: Optional[str] = None
    proof_metadata: Optional[Dict[str, Any]] = None
    proof_captured_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Route Models
class RouteBase(BaseModel):
    name: Optional[str] = None
    date: Optional[datetime] = None


class RouteCreate(RouteBase):
    driver_id: int
    order_ids: Optional[List[int]] = None


class RouteUpdate(BaseModel):
    name: Optional[str] = None
    driver_id: Optional[int] = None
    status: Optional[str] = None


class RouteOrderItem(BaseModel):
    order_id: int
    sequence: int


class Route(RouteBase):
    id: int
    driver_id: int
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class RouteWithOrders(Route):
    route_orders: List[Dict[str, Any]] = []


# Driver Update Models
class DriverUpdateCreate(BaseModel):
    driver_id: int
    route_id: Optional[int] = None
    order_id: Optional[int] = None
    update_type: str
    data: Optional[Dict[str, Any]] = None


class DriverUpdateResponse(BaseModel):
    id: int
    driver_id: int
    route_id: Optional[int] = None
    order_id: Optional[int] = None
    update_type: str
    data: Optional[Dict[str, Any]] = None
    created_at: datetime

    class Config:
        from_attributes = True


class DriverOrderAssignment(BaseModel):
    route_id: Optional[int] = None
    route_order_id: Optional[int] = None
    route_sequence: Optional[int] = None
    route_status: Optional[str] = None
    order: Order


class DriverStatusUpdateRequest(BaseModel):
    status: str
    notes: Optional[str] = None
    failure_reason: Optional[str] = None
    gps_lat: Optional[float] = None
    gps_lng: Optional[float] = None


# Phone Call / Text Parsing Models
class ParseTextRequest(BaseModel):
    text: str
    source: str = "phone"


# Route Planning Models
class PlanRoutesRequest(BaseModel):
    date: Optional[str] = None  # ISO date string
    max_distance_km: float = 10.0
    min_orders_per_route: int = 3
    max_orders_per_route: int = 40
    driver_ids: Optional[List[int]] = None
    clustering_method: str = "dbscan"  # "dbscan" or "kmeans"
    assignment_strategy: str = "balanced"  # "balanced" or "sequential"
