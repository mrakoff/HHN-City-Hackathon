import os
import uuid
import base64
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Header, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, case
from typing import List, Optional, Dict
from datetime import datetime
import re

from ..database import get_db, Order, Driver, Route, RouteOrder
from ..models import (
    OrderCreate,
    OrderUpdate,
    Order as OrderModel,
    ParseTextRequest,
    DriverOrderAssignment,
    DriverStatusUpdateRequest,
)
from ..services.order_parser import parse_order_from_text
from ..services.order_validator import validate_order, calculate_priority_from_time_window
from ..services.geocoding import geocode_address

router = APIRouter(prefix="/api/orders", tags=["orders"])

# Toggle driver_id fallback only for local testing.
ALLOW_DRIVER_TEST_MODE = os.getenv("ALLOW_DRIVER_TEST_MODE", "false").lower() in {"1", "true", "yes"}
PROOF_UPLOAD_DIR = Path(os.getenv("PROOF_UPLOAD_DIR", "uploads/proof"))
ALLOWED_IMAGE_TYPES = {
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/webp",
    "image/heic",
    "image/heif",
}
IMAGE_SUFFIX_WHITELIST = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"}

DRIVER_STATUS_TO_ORDER_STATUS: Dict[str, str] = {
    "assigned": "assigned",
    "accepted": "assigned",
    "en_route": "in_transit",
    "arrived": "in_transit",
    "delivered": "completed",
    "failed": "failed",
    "issue_reported": "in_transit",
}

DRIVER_STATUS_TO_ROUTE_STATUS: Dict[str, str] = {
    "assigned": "pending",
    "accepted": "pending",
    "en_route": "in_transit",
    "arrived": "in_transit",
    "delivered": "completed",
    "failed": "failed",
}


def get_current_driver(
    db: Session = Depends(get_db),
    x_driver_code: Optional[str] = Header(
        default=None,
        alias="X-Driver-Code",
        convert_underscores=False,
        description="Authentication token issued to drivers",
    ),
    driver_id: Optional[int] = Query(
        default=None,
        description="Temporary fallback for manual testing without tokens",
    ),
) -> Driver:
    """
    Resolve the active driver from the X-Driver-Code header.
    If no token is provided, uses the first available driver (for development/testing).
    """
    if x_driver_code:
        driver = db.query(Driver).filter(Driver.access_code == x_driver_code).first()
        if not driver:
            raise HTTPException(status_code=401, detail="Invalid driver token")
        return driver

    if driver_id is not None:
        driver = db.query(Driver).filter(Driver.id == driver_id).first()
        if not driver:
            raise HTTPException(status_code=404, detail="Driver not found")
        return driver

    # If no token provided, use the first available driver (for development)
    driver = db.query(Driver).first()
    if not driver:
        raise HTTPException(status_code=404, detail="No drivers found in database")
    return driver


def _route_assignment_map(driver: Driver, db: Session) -> Dict[int, RouteOrder]:
    """Return the first RouteOrder per order for the provided driver, excluding completed/cancelled routes."""
    assignments: Dict[int, RouteOrder] = {}
    # Get orders from routes that are not completed or cancelled
    # Route statuses: planned, active, completed, cancelled
    route_rows = (
        db.query(RouteOrder)
        .join(Route, Route.id == RouteOrder.route_id)
        .filter(
            Route.driver_id == driver.id,
            Route.status.notin_(["completed", "cancelled"])
        )
        .order_by(RouteOrder.sequence.asc())
        .all()
    )
    for ro in route_rows:
        if ro.order_id not in assignments:
            assignments[ro.order_id] = ro
    return assignments


def _validate_image_upload(content_type: Optional[str], field_name: str) -> None:
    if content_type and content_type.lower() not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"{field_name} must be an image ({', '.join(sorted(ALLOWED_IMAGE_TYPES))})",
        )


def _build_asset_filename(prefix: str, original_filename: Optional[str]) -> str:
    suffix = Path(original_filename or "").suffix.lower()
    if suffix not in IMAGE_SUFFIX_WHITELIST:
        suffix = ".jpg"
    return f"{prefix}_{uuid.uuid4().hex}{suffix}"


async def _persist_upload_file(file: UploadFile, destination_dir: Path, prefix: str) -> Path:
    _validate_image_upload(file.content_type, prefix)
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail=f"{prefix.capitalize()} file is empty")

    filename = _build_asset_filename(prefix, file.filename)
    destination = destination_dir / filename
    destination.write_bytes(content)
    return destination


def _decode_base64_image(payload: str) -> bytes:
    data = payload.split(",", 1)[1] if "," in payload else payload
    try:
        return base64.b64decode(data)
    except Exception as exc:  # pragma: no cover - defensive branch
        raise HTTPException(status_code=400, detail="Invalid signature payload") from exc


def _ensure_driver_can_access_order(order: Order, driver: Driver, db: Session) -> Optional[RouteOrder]:
    """
    Ensure the driver has access to the provided order either through a direct
    assignment or because the order exists on one of their routes.
    """
    if order.assigned_driver_id == driver.id:
        return (
            db.query(RouteOrder)
            .join(Route, Route.id == RouteOrder.route_id)
            .filter(RouteOrder.order_id == order.id, Route.driver_id == driver.id)
            .order_by(RouteOrder.sequence.asc())
            .first()
        )

    route_order = (
        db.query(RouteOrder)
        .join(Route, Route.id == RouteOrder.route_id)
        .filter(RouteOrder.order_id == order.id, Route.driver_id == driver.id)
        .order_by(RouteOrder.sequence.asc())
        .first()
    )

    if not route_order:
        raise HTTPException(status_code=403, detail="Order not assigned to this driver")

    if order.assigned_driver_id is None:
        order.assigned_driver_id = driver.id
        order.driver_status = order.driver_status or "accepted"
        order.driver_status_updated_at = datetime.utcnow()

    return route_order


def _build_driver_assignment(order: Order, route_order: Optional[RouteOrder]) -> DriverOrderAssignment:
    return DriverOrderAssignment(
        route_id=route_order.route_id if route_order else None,
        route_order_id=route_order.id if route_order else None,
        route_sequence=route_order.sequence if route_order else None,
        route_status=route_order.status if route_order else order.driver_status,
        order=order,
    )


@router.get("/driver/orders", response_model=List[DriverOrderAssignment])
def list_driver_orders_for_driver(
    include_completed: bool = Query(
        False,
        description="Include delivered/failed orders in the driver feed",
    ),
    driver_id: Optional[int] = Query(
        None,
        description="Specific driver ID to get orders for (overrides authentication)",
    ),
    driver: Driver = Depends(get_current_driver),
    db: Session = Depends(get_db),
):
    # If driver_id is specified, use that driver instead
    if driver_id is not None:
        specified_driver = db.query(Driver).filter(Driver.id == driver_id).first()
        if not specified_driver:
            raise HTTPException(status_code=404, detail="Driver not found")
        driver = specified_driver

    assignments = _route_assignment_map(driver, db)
    orders_by_id: Dict[int, Order] = {}

    # Only include orders that are in active routes
    # This ensures drivers only see orders that are part of their planned routes
    if assignments:
        order_ids = list(assignments.keys())
        route_orders = db.query(Order).filter(Order.id.in_(order_ids)).all()
        for order in route_orders:
            orders_by_id[order.id] = order

    def is_completed(order: Order) -> bool:
        status = (order.driver_status or order.status or "").lower()
        return status in {"delivered", "failed", "completed", "cancelled"}

    # Sort orders: prioritize route_sequence when available, then by timestamp
    def sort_key(order: Order) -> tuple:
        route_order = assignments.get(order.id)
        if route_order and route_order.sequence is not None:
            # Orders with route sequence come first, sorted by sequence
            return (0, route_order.sequence)
        else:
            # Orders without route sequence come after, sorted by timestamp (newest first)
            timestamp = order.driver_status_updated_at or order.updated_at or order.created_at
            return (1, -(timestamp.timestamp() if timestamp else 0))

    sorted_orders = sorted(
        orders_by_id.values(),
        key=sort_key,
    )

    payload: List[DriverOrderAssignment] = []
    for order in sorted_orders:
        if not include_completed and is_completed(order):
            continue
        route_order = assignments.get(order.id)
        payload.append(_build_driver_assignment(order, route_order))

    return payload


@router.get("/driver/orders/{order_id}", response_model=DriverOrderAssignment)
def get_driver_order_detail(
    order_id: int,
    driver: Driver = Depends(get_current_driver),
    db: Session = Depends(get_db),
):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    route_order = _ensure_driver_can_access_order(order, driver, db)
    db.commit()
    db.refresh(order)
    return _build_driver_assignment(order, route_order)


@router.get("/driver/orders/{order_id}/directions")
def get_driver_order_directions(
    order_id: int,
    driver_id: Optional[int] = Query(
        None,
        description="Specific driver ID (overrides authentication)",
    ),
    driver: Driver = Depends(get_current_driver),
    db: Session = Depends(get_db),
):
    """
    Get turn-by-turn directions for a specific order.
    Returns route visualization and navigation instructions.
    """
    from ..database import Route, RouteOrder, Depot
    from ..services.osrm_client import get_route, check_osrm_available
    from ..services.route_calculator import calculate_complete_route

    # If driver_id is specified, use that driver instead
    if driver_id is not None:
        specified_driver = db.query(Driver).filter(Driver.id == driver_id).first()
        if not specified_driver:
            raise HTTPException(status_code=404, detail="Driver not found")
        driver = specified_driver

    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    route_order = _ensure_driver_can_access_order(order, driver, db)
    if not route_order:
        raise HTTPException(status_code=404, detail="Order not found in any route")

    # Get the route
    route = db.query(Route).filter(Route.id == route_order.route_id).first()
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")

    # Get all route orders for this route
    all_route_orders = db.query(RouteOrder).filter(
        RouteOrder.route_id == route.id
    ).order_by(RouteOrder.sequence).all()

    # Get depot
    depot = db.query(Depot).first()
    if not depot:
        driver = db.query(Driver).filter(Driver.id == route.driver_id).first()
        if driver and driver.current_location_lat and driver.current_location_lng:
            depot_dict = {
                "id": None,
                "name": "Driver Location",
                "latitude": driver.current_location_lat,
                "longitude": driver.current_location_lng
            }
        else:
            raise HTTPException(
                status_code=400,
                detail="No depot found and driver has no location"
            )
    else:
        if not depot.latitude or not depot.longitude:
            raise HTTPException(
                status_code=400,
                detail=f"Depot '{depot.name}' is missing coordinates"
            )
        depot_dict = {
            "id": depot.id,
            "name": depot.name,
            "latitude": depot.latitude,
            "longitude": depot.longitude
        }

    # Get order locations
    orders_data = []
    target_order_idx = None
    for idx, ro in enumerate(all_route_orders):
        o = db.query(Order).filter(Order.id == ro.order_id).first()
        if o and o.latitude and o.longitude:
            orders_data.append({
                "id": o.id,
                "order_number": o.order_number,
                "latitude": o.latitude,
                "longitude": o.longitude,
                "delivery_address": o.delivery_address,
                "customer_name": o.customer_name,
                "order": o
            })
            if o.id == order_id:
                target_order_idx = len(orders_data) - 1

    if not orders_data:
        raise HTTPException(status_code=400, detail="No orders with valid coordinates in route")

    # Calculate complete route
    try:
        from datetime import datetime
        complete_route = calculate_complete_route(
            depot=depot_dict,
            orders=orders_data,
            parking_locations=[],  # Will use dynamic parking
            optimized_order_indices=None,  # Use current sequence
            start_time=datetime.utcnow()
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error calculating route: {str(e)}")

    # Get turn-by-turn directions using OSRM
    directions = []
    waypoints = complete_route["waypoints"]

    if check_osrm_available() and len(waypoints) >= 2:
        # Get directions for each segment
        for i in range(len(waypoints) - 1):
            current = waypoints[i]
            next_wp = waypoints[i + 1]

            route_data = get_route(
                current["lat"], current["lon"],
                next_wp["lat"], next_wp["lon"],
                steps=True,
                overview="full",
                geometries="geojson"
            )

            if route_data and route_data.get("legs") and len(route_data["legs"]) > 0:
                leg = route_data["legs"][0]
                # OSRM returns steps in leg.steps when steps=true
                steps = leg.get("steps", [])
                for step in steps:
                    maneuver = step.get("maneuver", {})
                    instruction_text = maneuver.get("instruction", "")
                    if not instruction_text:
                        # Fallback: create instruction from type and modifier
                        maneuver_type = maneuver.get("type", "")
                        modifier = maneuver.get("modifier", "")
                        if maneuver_type == "turn":
                            if modifier:
                                instruction_text = f"Turn {modifier}"
                            else:
                                instruction_text = "Turn"
                        elif maneuver_type == "new name":
                            instruction_text = "Continue straight"
                        elif maneuver_type == "depart":
                            instruction_text = "Start"
                        elif maneuver_type == "arrive":
                            instruction_text = "Arrive at destination"
                        else:
                            instruction_text = maneuver_type.replace("_", " ").title()

                    directions.append({
                        "distance": step.get("distance", 0),  # meters
                        "duration": step.get("duration", 0),  # seconds
                        "instruction": instruction_text,
                        "type": maneuver.get("type", ""),
                        "modifier": maneuver.get("modifier", ""),
                        "geometry": step.get("geometry"),
                        "waypoint_index": i,
                        "waypoint_type": current.get("type", "unknown")
                    })

    return {
        "order_id": order_id,
        "route_id": route.id,
        "route_name": route.name,
        "waypoints": [
            {
                "type": wp["type"],
                "lat": wp["lat"],
                "lon": wp["lon"],
                "metadata": wp.get("metadata", {}),
                "estimated_arrival": wp.get("estimated_arrival")
            }
            for wp in waypoints
        ],
        "directions": directions,
        "geometry": complete_route.get("geometry"),
        "total_distance_km": complete_route["total_distance_km"],
        "total_time_minutes": complete_route["total_time_minutes"],
        "target_order_index": target_order_idx
    }


@router.post("/driver/orders/{order_id}/status", response_model=OrderModel)
def update_driver_order_status(
    order_id: int,
    payload: DriverStatusUpdateRequest,
    driver_id: Optional[int] = Query(
        None,
        description="Specific driver ID (overrides authentication)",
    ),
    driver: Driver = Depends(get_current_driver),
    db: Session = Depends(get_db),
):
    # If driver_id is specified, use that driver instead
    if driver_id is not None:
        specified_driver = db.query(Driver).filter(Driver.id == driver_id).first()
        if not specified_driver:
            raise HTTPException(status_code=404, detail="Driver not found")
        driver = specified_driver

    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    route_order = _ensure_driver_can_access_order(order, driver, db)
    now = datetime.utcnow()

    normalized_status = (payload.status or "").lower()
    order.assigned_driver_id = driver.id
    order.driver_status = normalized_status
    order.driver_notes = payload.notes
    order.failure_reason = payload.failure_reason
    order.driver_gps_lat = payload.gps_lat
    order.driver_gps_lng = payload.gps_lng
    order.driver_status_updated_at = now

    mapped_status = DRIVER_STATUS_TO_ORDER_STATUS.get(normalized_status)
    if mapped_status:
        order.status = mapped_status
    if normalized_status == "delivered":
        order.delivered_at = now
    if normalized_status == "failed":
        order.failed_at = now

    if route_order:
        route_status = DRIVER_STATUS_TO_ROUTE_STATUS.get(normalized_status)
        if route_status:
            route_order.status = route_status
        if normalized_status in {"arrived", "delivered"}:
            route_order.actual_arrival = route_order.actual_arrival or now

    driver.last_check_in_at = now
    if normalized_status in {"accepted", "en_route", "arrived"}:
        driver.status = "on_route"
    elif normalized_status in {"delivered", "failed"}:
        driver.status = "available"

    db.commit()
    db.refresh(order)
    return order


@router.post("/driver/orders/{order_id}/proof", response_model=OrderModel)
async def upload_driver_proof_of_delivery(
    order_id: int,
    photo: Optional[UploadFile] = File(
        None, description="Photo captured at delivery (JPEG/PNG/WEBP)"
    ),
    signature: Optional[UploadFile] = File(
        None, description="Signature image file captured by driver"
    ),
    signature_data: Optional[str] = Form(
        None, description="Base64 encoded signature from canvas widget"
    ),
    notes: Optional[str] = Form(None),
    gps_lat: Optional[float] = Form(None),
    gps_lng: Optional[float] = Form(None),
    driver_id: Optional[int] = Form(
        None,
        description="Specific driver ID (overrides authentication)",
    ),
    driver: Driver = Depends(get_current_driver),
    db: Session = Depends(get_db),
):
    """
    Upload proof-of-delivery artifacts (photo + signature).
    Drivers must supply their X-Driver-Code header. Files are stored under uploads/proof/.
    """
    # If driver_id is specified, use that driver instead
    if driver_id is not None:
        specified_driver = db.query(Driver).filter(Driver.id == driver_id).first()
        if not specified_driver:
            raise HTTPException(status_code=404, detail="Driver not found")
        driver = specified_driver

    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    route_order = _ensure_driver_can_access_order(order, driver, db)

    if not any([photo, signature, signature_data]):
        raise HTTPException(status_code=400, detail="Provide at least a photo or signature payload")

    PROOF_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    order_dir = PROOF_UPLOAD_DIR / f"order_{order_id}"
    order_dir.mkdir(parents=True, exist_ok=True)

    saved_photo = None
    saved_signature = None

    if photo:
        saved_photo = await _persist_upload_file(photo, order_dir, "photo")
        order.proof_photo_path = str(saved_photo)

    if signature:
        saved_signature = await _persist_upload_file(signature, order_dir, "signature")
        order.proof_signature_path = str(saved_signature)
    elif signature_data:
        signature_bytes = _decode_base64_image(signature_data)
        filename = order_dir / _build_asset_filename("signature", "signature.png")
        filename.write_bytes(signature_bytes)
        order.proof_signature_path = str(filename)
        saved_signature = filename

    now = datetime.utcnow()
    metadata = order.proof_metadata or {}
    metadata["uploaded_by_driver_id"] = driver.id
    metadata["uploaded_at"] = now.isoformat()
    if saved_photo:
        metadata["photo_filename"] = saved_photo.name
    if saved_signature:
        metadata["signature_filename"] = saved_signature.name
    if notes:
        metadata["notes"] = notes
    if gps_lat is not None and gps_lng is not None:
        metadata["gps"] = {"lat": gps_lat, "lng": gps_lng}

    if gps_lat is not None:
        order.driver_gps_lat = gps_lat
    if gps_lng is not None:
        order.driver_gps_lng = gps_lng
    if notes:
        order.driver_notes = notes

    order.proof_metadata = metadata
    order.proof_captured_at = now
    order.driver_status_updated_at = now
    order.assigned_driver_id = driver.id
    driver.last_check_in_at = now

    if order.driver_status not in {"delivered", "failed"}:
        order.driver_status = "delivered"
        order.status = "completed"
        order.delivered_at = order.delivered_at or now

    if route_order:
        route_order.status = "completed"
        route_order.actual_arrival = route_order.actual_arrival or now

    db.commit()
    db.refresh(order)
    return order


def generate_order_number(db: Session) -> str:
    """Generate order number in format ORD-ddmmyy-XXXX"""
    now = datetime.now()
    date_str = now.strftime("%d%m%y")  # ddmmyy format

    # Find the highest sequential number for today
    prefix = f"ORD-{date_str}-"

    # Query all orders with today's prefix
    existing_orders = db.query(Order.order_number).filter(
        Order.order_number.like(f"{prefix}%")
    ).all()

    max_seq = 0
    for order_num_tuple in existing_orders:
        order_num = order_num_tuple[0]
        # Extract the 4-digit sequence number
        match = re.search(rf"^{re.escape(prefix)}(\d{{4}})$", order_num)
        if match:
            seq_num = int(match.group(1))
            max_seq = max(max_seq, seq_num)

    # Increment and format as 4-digit zero-padded number
    next_seq = max_seq + 1
    return f"{prefix}{next_seq:04d}"


def ensure_unique_order_number(order_data: OrderCreate, db: Session) -> OrderCreate:
    """Ensure order_number is unique, generate new one if missing or conflicting"""
    if not order_data.order_number:
        # Generate a new order number if none provided
        order_data.order_number = generate_order_number(db)
    else:
        # Check if the provided order number already exists
        existing_order = db.query(Order).filter(Order.order_number == order_data.order_number).first()
        if existing_order:
            # Generate a new unique order number in the correct format
            order_data.order_number = generate_order_number(db)
    return order_data


def prepare_order_for_db(order_data: OrderCreate, db: Session) -> Order:
    """
    Normalize an OrderCreate payload before persisting:
    - ensure unique order number
    - auto-calculate priority when missing
    - geocode addresses via OSM (Nominatim) when coordinates missing
    - run validation and attach validation errors
    """
    order_data = ensure_unique_order_number(order_data, db)
    if not order_data.driver_status:
        order_data.driver_status = "unassigned"

    if not order_data.priority:
        order_data.priority = calculate_priority_from_time_window(
            order_data.delivery_time_window_start,
            order_data.delivery_time_window_end
        )

    if order_data.delivery_address and (
        not order_data.latitude or not order_data.longitude
    ):
        coords = geocode_address(order_data.delivery_address)
        if coords:
            order_data.latitude = coords["lat"]
            order_data.longitude = coords["lon"]

    validation_errors = validate_order(order_data)
    order_dict = order_data.dict()
    db_order = Order(**order_dict)
    if validation_errors:
        db_order.validation_errors = validation_errors

    return db_order


@router.post("/", response_model=OrderModel)
def create_order(order: OrderCreate, db: Session = Depends(get_db)):
    """Create a new order"""
    db_order = prepare_order_for_db(order, db)
    db.add(db_order)
    db.commit()
    db.refresh(db_order)
    return db_order


@router.post("/bulk", response_model=List[OrderModel])
def create_orders_bulk(orders: List[OrderCreate], db: Session = Depends(get_db)):
    """
    Create multiple orders in a single transaction.
    Handles geocoding for addresses without coordinates and generates unique order numbers.
    """
    created_orders = []

    try:
        for order in orders:
            db_order = prepare_order_for_db(order, db)
            db.add(db_order)
            db.flush()  # Ensure generated order numbers are visible for subsequent inserts
            created_orders.append(db_order)

        db.commit()

        # Refresh all orders to get IDs
        for order in created_orders:
            db.refresh(order)

        return created_orders

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Error creating orders: {str(e)}")


@router.get("/", response_model=List[OrderModel])
def get_orders(
    status: Optional[str] = None,
    source: Optional[str] = None,
    unfinished: Optional[bool] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Get all orders with optional filters"""
    query = db.query(Order)

    if status:
        query = query.filter(Order.status == status)
    if source:
        query = query.filter(Order.source == source)
    if unfinished is not None and unfinished:
        # Unfinished orders: have validation errors or missing critical fields
        query = query.filter(
            or_(
                # Has validation errors (not None - empty lists will be filtered in Python)
                Order.validation_errors.isnot(None),
                # Missing delivery address
                Order.delivery_address == None,
                Order.delivery_address == ""
            )
        )

    # Sort orders: priority first (urgent > high > normal > low), then by created_at (newest first)
    # Apply sorting
    query = query.order_by(
        # Sort by priority (custom order)
        case(
            (Order.priority == 'urgent', 1),
            (Order.priority == 'high', 2),
            (Order.priority == 'normal', 3),
            (Order.priority == 'low', 4),
            else_=5  # Unknown/null priority goes last
        ),
        # Then by created_at descending (newest first)
        Order.created_at.desc()
    )

    orders = query.offset(skip).limit(limit).all()

    # Filter out orders with empty validation_errors lists (they're not unfinished)
    if unfinished is not None and unfinished:
        orders = [
            order for order in orders
            if (
                # Has non-empty validation errors
                (order.validation_errors is not None and
                 isinstance(order.validation_errors, list) and
                 len(order.validation_errors) > 0) or
                # Missing delivery address
                not order.delivery_address or
                order.delivery_address.strip() == ""
            )
        ]

    return orders


@router.get("/{order_id}", response_model=OrderModel)
def get_order(order_id: int, db: Session = Depends(get_db)):
    """Get a specific order by ID"""
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@router.put("/{order_id}", response_model=OrderModel)
def update_order(order_id: int, order_update: OrderUpdate, db: Session = Depends(get_db)):
    """Update an order"""
    db_order = db.query(Order).filter(Order.id == order_id).first()
    if not db_order:
        raise HTTPException(status_code=404, detail="Order not found")

    update_data = order_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_order, field, value)

    db_order.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(db_order)
    return db_order


@router.delete("/{order_id}")
def delete_order(order_id: int, db: Session = Depends(get_db)):
    """Delete an order"""
    db_order = db.query(Order).filter(Order.id == order_id).first()
    if not db_order:
        raise HTTPException(status_code=404, detail="Order not found")

    db.delete(db_order)
    db.commit()
    return {"message": "Order deleted successfully"}


@router.post("/upload", response_model=OrderModel)
async def upload_order_document(
    file: UploadFile = File(...),
    source: str = Form("email"),
    db: Session = Depends(get_db)
):
    """Upload and parse order from document (email attachment, fax, mail scan)"""
    from ..services.order_parser import parse_document

    # Save uploaded file temporarily
    import aiofiles
    import os
    from pathlib import Path
    import uuid

    os.makedirs("uploads", exist_ok=True)
    # Use a unique filename to avoid conflicts and path traversal issues
    safe_filename = os.path.basename(file.filename) if file.filename else "upload"
    file_ext = Path(safe_filename).suffix
    unique_filename = f"{uuid.uuid4().hex}{file_ext}"
    file_path = os.path.join("uploads", unique_filename)

    async with aiofiles.open(file_path, 'wb') as out_file:
        content = await file.read()
        await out_file.write(content)

    # Parse document
    try:
        parsed_data = await parse_document(file_path)

        # Create order from parsed data
        order_data = OrderCreate(
            order_number=parsed_data.get("order_number"),
            delivery_address=parsed_data.get("delivery_address", ""),
            customer_name=parsed_data.get("customer_name"),
            customer_phone=parsed_data.get("customer_phone"),
            customer_email=parsed_data.get("customer_email"),
            description=parsed_data.get("description"),
            items=parsed_data.get("items"),
            delivery_time_window_start=parsed_data.get("delivery_time_window_start"),
            delivery_time_window_end=parsed_data.get("delivery_time_window_end"),
            priority=None,  # Will be calculated automatically
            source=source,
            raw_text=parsed_data.get("raw_text")
        )

        db_order = prepare_order_for_db(order_data, db)
        db.add(db_order)
        db.commit()
        db.refresh(db_order)

        # Clean up uploaded file
        os.remove(file_path)

        return db_order

    except Exception as e:
        # Clean up on error
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=400, detail=f"Error parsing document: {str(e)}")


@router.post("/parse-text-only")
def parse_text_only(
    request: ParseTextRequest
):
    """Parse order from text and return parsed data without creating an order (for form population)"""
    try:
        text = request.text
        parsed_data = parse_order_from_text(text)

        # Return parsed data in a format suitable for form population
        return {
            "customer_name": parsed_data.get("customer_name"),
            "customer_phone": parsed_data.get("customer_phone"),
            "customer_email": parsed_data.get("customer_email"),
            "delivery_address": parsed_data.get("delivery_address", ""),
            "description": parsed_data.get("description"),
            "delivery_time_window_start": parsed_data.get("delivery_time_window_start"),
            "delivery_time_window_end": parsed_data.get("delivery_time_window_end"),
            "raw_text": parsed_data.get("raw_text", text)
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error parsing text: {str(e)}")


@router.post("/parse-text", response_model=OrderModel)
def parse_order_text(
    request: ParseTextRequest,
    db: Session = Depends(get_db)
):
    """Parse order from text (e.g., from phone call)"""
    try:
        text = request.text
        source = request.source
        parsed_data = parse_order_from_text(text)

        order_data = OrderCreate(
            order_number=parsed_data.get("order_number"),
            delivery_address=parsed_data.get("delivery_address", ""),
            customer_name=parsed_data.get("customer_name"),
            customer_phone=parsed_data.get("customer_phone"),
            customer_email=parsed_data.get("customer_email"),
            description=parsed_data.get("description"),
            items=parsed_data.get("items"),
            delivery_time_window_start=parsed_data.get("delivery_time_window_start"),
            delivery_time_window_end=parsed_data.get("delivery_time_window_end"),
            priority=None,  # Will be calculated automatically
            source=source,
            raw_text=text
        )

        db_order = prepare_order_for_db(order_data, db)
        db.add(db_order)
        db.commit()
        db.refresh(db_order)

        return db_order

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error parsing text: {str(e)}")


@router.post("/transcribe-audio")
async def transcribe_audio_chunk(
    audio: UploadFile = File(...),
    language: Optional[str] = Form(None)
):
    """Transcribe an audio chunk using local Whisper model (no API key needed)
    Uses the open-source Whisper model running locally on the server.
    """
    from ..services.speech_to_text import transcribe_audio_bytes
    import traceback

    try:
        # Read audio file content
        audio_bytes = await audio.read()
        filename = audio.filename or "audio.webm"

        if len(audio_bytes) == 0:
            raise HTTPException(status_code=400, detail="Empty audio file received")

        print(f"Received audio file: {filename}, size: {len(audio_bytes)} bytes")

        # Transcribe audio using local Whisper model
        transcription = transcribe_audio_bytes(audio_bytes, filename=filename, language=language)

        return {
            "transcription": transcription,
            "success": True
        }
    except HTTPException:
        raise
    except Exception as e:
        error_detail = str(e)
        error_trace = traceback.format_exc()
        print(f"Transcription error: {error_detail}")
        print(f"Traceback: {error_trace}")

        # Return user-friendly error message
        if "corrupted" in error_detail.lower() or "incomplete" in error_detail.lower() or "invalid data" in error_detail.lower():
            user_message = "The audio recording could not be processed. Please try recording again and make sure to speak clearly."
        elif "too small" in error_detail.lower() or "too short" in error_detail.lower():
            user_message = "The recording is too short. Please record for at least a few seconds."
        else:
            user_message = "Unable to transcribe the audio. Please try recording again."

        raise HTTPException(
            status_code=500,
            detail=user_message
        )


@router.post("/transcribe-audio-final")
async def transcribe_audio_final(
    audio: UploadFile = File(...),
    language: Optional[str] = Form(None)
):
    """Transcribe complete audio file and return full transcription"""
    from ..services.speech_to_text import transcribe_audio_bytes

    try:
        # Read audio file content
        audio_bytes = await audio.read()
        filename = audio.filename or "audio.webm"

        # Transcribe audio
        transcription = transcribe_audio_bytes(audio_bytes, filename=filename, language=language)

        return {
            "transcription": transcription,
            "success": True
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error transcribing audio: {str(e)}")


@router.post("/receive-email", response_model=OrderModel)
async def receive_email_order(
    sender_email: Optional[str] = Form(None),
    email_body: Optional[str] = Form(None),
    attachment: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    """Simulate receiving an order via email with optional attachment"""
    from ..services.order_parser import parse_document
    import aiofiles
    import os

    parsed_data = None
    file_path = None

    try:
        # If there's an attachment, parse it
        if attachment:
            os.makedirs("uploads", exist_ok=True)
            file_path = f"uploads/{attachment.filename}"

            async with aiofiles.open(file_path, 'wb') as out_file:
                content = await attachment.read()
                await out_file.write(content)

            parsed_data = await parse_document(file_path)

            # Clean up uploaded file
            if os.path.exists(file_path):
                os.remove(file_path)
                file_path = None
        # Otherwise, parse email body text
        elif email_body:
            parsed_data = parse_order_from_text(email_body)
        else:
            raise HTTPException(status_code=400, detail="Either attachment or email_body must be provided")

        # Create order from parsed data
        order_data = OrderCreate(
            order_number=parsed_data.get("order_number"),
            delivery_address=parsed_data.get("delivery_address", ""),
            customer_name=parsed_data.get("customer_name"),
            customer_phone=parsed_data.get("customer_phone"),
            customer_email=sender_email or parsed_data.get("customer_email"),
            description=parsed_data.get("description"),
            items=parsed_data.get("items"),
            delivery_time_window_start=parsed_data.get("delivery_time_window_start"),
            delivery_time_window_end=parsed_data.get("delivery_time_window_end"),
            priority=None,  # Will be calculated automatically
            source="email",
            raw_text=parsed_data.get("raw_text") or email_body
        )

        db_order = prepare_order_for_db(order_data, db)
        db.add(db_order)
        db.commit()
        db.refresh(db_order)

        return db_order

    except HTTPException:
        raise
    except Exception as e:
        # Clean up on error
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=400, detail=f"Error processing email order: {str(e)}")


@router.post("/receive-fax", response_model=OrderModel)
async def receive_fax_order(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Simulate receiving an order via fax"""
    from ..services.order_parser import parse_document
    import aiofiles
    import os

    os.makedirs("uploads", exist_ok=True)
    file_path = f"uploads/{file.filename}"

    async with aiofiles.open(file_path, 'wb') as out_file:
        content = await file.read()
        await out_file.write(content)

    # Parse document
    try:
        parsed_data = await parse_document(file_path)

        # Create order from parsed data
        order_data = OrderCreate(
            order_number=parsed_data.get("order_number"),
            delivery_address=parsed_data.get("delivery_address", ""),
            customer_name=parsed_data.get("customer_name"),
            customer_phone=parsed_data.get("customer_phone"),
            customer_email=parsed_data.get("customer_email"),
            description=parsed_data.get("description"),
            items=parsed_data.get("items"),
            delivery_time_window_start=parsed_data.get("delivery_time_window_start"),
            delivery_time_window_end=parsed_data.get("delivery_time_window_end"),
            priority=None,  # Will be calculated automatically
            source="fax",
            raw_text=parsed_data.get("raw_text")
        )

        db_order = prepare_order_for_db(order_data, db)
        db.add(db_order)
        db.commit()
        db.refresh(db_order)

        # Clean up uploaded file
        os.remove(file_path)

        return db_order

    except Exception as e:
        # Clean up on error
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=400, detail=f"Error parsing fax document: {str(e)}")


@router.post("/receive-mail", response_model=OrderModel)
async def receive_mail_order(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Simulate receiving an order via scanned physical mail"""
    from ..services.order_parser import parse_document
    import aiofiles
    import os

    os.makedirs("uploads", exist_ok=True)
    file_path = f"uploads/{file.filename}"

    async with aiofiles.open(file_path, 'wb') as out_file:
        content = await file.read()
        await out_file.write(content)

    # Parse document
    try:
        parsed_data = await parse_document(file_path)

        # Create order from parsed data
        order_data = OrderCreate(
            order_number=parsed_data.get("order_number"),
            delivery_address=parsed_data.get("delivery_address", ""),
            customer_name=parsed_data.get("customer_name"),
            customer_phone=parsed_data.get("customer_phone"),
            customer_email=parsed_data.get("customer_email"),
            description=parsed_data.get("description"),
            items=parsed_data.get("items"),
            delivery_time_window_start=parsed_data.get("delivery_time_window_start"),
            delivery_time_window_end=parsed_data.get("delivery_time_window_end"),
            priority=None,  # Will be calculated automatically
            source="mail",
            raw_text=parsed_data.get("raw_text")
        )

        db_order = prepare_order_for_db(order_data, db)
        db.add(db_order)
        db.commit()
        db.refresh(db_order)

        # Clean up uploaded file
        os.remove(file_path)

        return db_order

    except Exception as e:
        # Clean up on error
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=400, detail=f"Error parsing mail document: {str(e)}")
