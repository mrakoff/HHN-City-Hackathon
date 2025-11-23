from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean, ForeignKey, Text, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime

SQLALCHEMY_DATABASE_URL = "sqlite:///./route_planning.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


class Driver(Base):
    __tablename__ = "drivers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    phone = Column(String)
    email = Column(String)
    status = Column(String, default="available")  # available, on_route, offline
    access_code = Column(String, unique=True, index=True)  # simple driver auth token
    current_location_lat = Column(Float)
    current_location_lng = Column(Float)
    last_check_in_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)

    routes = relationship("Route", back_populates="driver")


class Depot(Base):
    __tablename__ = "depots"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    address = Column(String, nullable=False)
    latitude = Column(Float)
    longitude = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)


class ParkingLocation(Base):
    __tablename__ = "parking_locations"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    address = Column(String, nullable=False)
    latitude = Column(Float)
    longitude = Column(Float)
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    order_number = Column(String, unique=True, index=True)
    customer_name = Column(String)
    customer_phone = Column(String)
    customer_email = Column(String)
    delivery_address = Column(String, nullable=False)
    description = Column(Text)  # Order description/notes
    latitude = Column(Float)
    longitude = Column(Float)
    items = Column(JSON)  # List of items with quantities
    delivery_time_window_start = Column(DateTime)
    delivery_time_window_end = Column(DateTime)
    priority = Column(String, default="normal")  # low, normal, high, urgent
    status = Column(String, default="pending")  # pending, assigned, in_transit, completed, failed
    driver_status = Column(String, default="unassigned")  # unassigned, accepted, en_route, delivered, failed
    failure_reason = Column(Text)
    driver_notes = Column(Text)
    driver_status_updated_at = Column(DateTime)
    source = Column(String)  # email, fax, mail, phone
    raw_text = Column(Text)  # Original scanned/parsed text
    validation_errors = Column(JSON)  # List of validation errors
    assigned_driver_id = Column(Integer, ForeignKey("drivers.id"))
    driver_gps_lat = Column(Float)
    driver_gps_lng = Column(Float)
    delivered_at = Column(DateTime)
    failed_at = Column(DateTime)
    proof_photo_path = Column(String)
    proof_signature_path = Column(String)
    proof_metadata = Column(JSON)
    proof_captured_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    route_orders = relationship("RouteOrder", back_populates="order")
    assigned_driver = relationship("Driver", foreign_keys=[assigned_driver_id])


class Route(Base):
    __tablename__ = "routes"

    id = Column(Integer, primary_key=True, index=True)
    driver_id = Column(Integer, ForeignKey("drivers.id"))
    name = Column(String)
    date = Column(DateTime, default=datetime.utcnow)
    status = Column(String, default="planned")  # planned, active, completed, cancelled
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    driver = relationship("Driver", back_populates="routes")
    route_orders = relationship("RouteOrder", back_populates="route", cascade="all, delete-orphan")


class RouteOrder(Base):
    __tablename__ = "route_orders"

    id = Column(Integer, primary_key=True, index=True)
    route_id = Column(Integer, ForeignKey("routes.id"), nullable=False)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    sequence = Column(Integer, nullable=False)  # Order in the route
    estimated_arrival = Column(DateTime)
    actual_arrival = Column(DateTime)
    status = Column(String, default="pending")  # pending, in_transit, completed, failed
    notes = Column(Text)

    route = relationship("Route", back_populates="route_orders")
    order = relationship("Order", back_populates="route_orders")


class RouteWaypoint(Base):
    __tablename__ = "route_waypoints"

    id = Column(Integer, primary_key=True, index=True)
    route_id = Column(Integer, ForeignKey("routes.id"), nullable=False)
    sequence = Column(Integer, nullable=False)  # Order in the route
    waypoint_type = Column(String, nullable=False)  # depot, parking, delivery
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    location_id = Column(Integer)  # ID of depot, parking_location, or order
    location_type = Column(String)  # depot, parking_location, order
    waypoint_data = Column(JSON)  # Additional waypoint data (renamed from metadata)
    estimated_arrival = Column(DateTime)
    actual_arrival = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)

    route = relationship("Route")


class DriverUpdate(Base):
    __tablename__ = "driver_updates"

    id = Column(Integer, primary_key=True, index=True)
    driver_id = Column(Integer, ForeignKey("drivers.id"), nullable=False)
    route_id = Column(Integer, ForeignKey("routes.id"))
    order_id = Column(Integer, ForeignKey("orders.id"))
    update_type = Column(String, nullable=False)  # location_update, order_completed, order_failed, route_update_accepted, route_update_rejected, problem_reported
    data = Column(JSON)  # Additional data (problem description, location, etc.)
    created_at = Column(DateTime, default=datetime.utcnow)


def init_db():
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
