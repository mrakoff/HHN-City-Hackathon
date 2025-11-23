import json
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..database import get_db, Route, RouteOrder, Order, Driver, Depot, ParkingLocation
from ..models import (
    RouteCreate, RouteUpdate, Route as RouteModel,
    RouteOrderItem, RouteWithOrders, OrderCreate, PlanRoutesRequest
)
from ..services.route_optimizer import optimize_route, calculate_route_improvement
from ..services.route_calculator import calculate_complete_route
from ..services.ai_agents import suggest_route_optimization
from ..services.route_clustering import cluster_orders
from ..services.driver_assigner import assign_drivers_to_clusters, calculate_route_statistics
from .orders import prepare_order_for_db

router = APIRouter(prefix="/api/routes", tags=["routes"])

PARKING_BBOX_PADDING_DEGREES = 0.03  # ~3 km latitude/longitude padding
PARKING_LIMIT_PER_ROUTE = 4000


def _extract_source_from_notes(notes: Optional[str]) -> Optional[str]:
    if not notes:
        return None
    try:
        payload = json.loads(notes)
        if isinstance(payload, dict):
            return payload.get("source")
    except (ValueError, TypeError):
        return None
    return None


def _collect_route_coordinates(depot_dict, orders_data) -> List[tuple]:
    coords: List[tuple] = []
    depot_lat = depot_dict.get("latitude") or depot_dict.get("lat")
    depot_lon = depot_dict.get("longitude") or depot_dict.get("lon")
    if depot_lat and depot_lon:
        coords.append((depot_lat, depot_lon))

    for order in orders_data:
        lat = order.get("latitude") or order.get("lat")
        lon = order.get("longitude") or order.get("lon")
        if lat and lon:
            coords.append((lat, lon))
    return coords


def _load_relevant_parking_locations(
    db: Session,
    depot_dict,
    orders_data,
    padding_degrees: float = PARKING_BBOX_PADDING_DEGREES,
    limit: int = PARKING_LIMIT_PER_ROUTE
):
    coords = _collect_route_coordinates(depot_dict, orders_data)
    if not coords:
        return []

    min_lat = min(lat for lat, _ in coords) - padding_degrees
    max_lat = max(lat for lat, _ in coords) + padding_degrees
    min_lon = min(lon for _, lon in coords) - padding_degrees
    max_lon = max(lon for _, lon in coords) + padding_degrees

    query = db.query(ParkingLocation).filter(
        ParkingLocation.latitude >= min_lat,
        ParkingLocation.latitude <= max_lat,
        ParkingLocation.longitude >= min_lon,
        ParkingLocation.longitude <= max_lon
    )

    parking_locations = query.limit(limit).all()
    if not parking_locations:
        parking_locations = db.query(ParkingLocation).limit(limit).all()

    parking_data = []
    for location in parking_locations:
        if location.latitude is None or location.longitude is None:
            continue
        parking_data.append({
            "id": location.id,
            "name": location.name,
            "latitude": location.latitude,
            "longitude": location.longitude,
            "address": location.address,
            "notes": location.notes,
            "source": _extract_source_from_notes(location.notes) or "db"
        })

    return parking_data


@router.post("/", response_model=RouteWithOrders)
def create_route(route: RouteCreate, db: Session = Depends(get_db)):
    """Create a new route"""
    # Verify driver exists
    driver = db.query(Driver).filter(Driver.id == route.driver_id).first()
    if not driver:
        raise HTTPException(status_code=404, detail="Driver not found")

    # Create route without order_ids
    route_data = route.dict()
    order_ids = route_data.pop('order_ids', None)
    db_route = Route(**route_data)
    db.add(db_route)
    db.commit()
    db.refresh(db_route)

    # Add orders if provided
    if order_ids:
        for sequence, order_id in enumerate(order_ids, 1):
            # Verify order exists
            order = db.query(Order).filter(Order.id == order_id).first()
            if not order:
                raise HTTPException(status_code=404, detail=f"Order {order_id} not found")

            # Update order status
            order.assigned_driver_id = route.driver_id
            order.driver_status = order.driver_status or "assigned"
            order.driver_status_updated_at = datetime.utcnow()
            order.status = "assigned"

            # Create route order
            route_order = RouteOrder(
                route_id=db_route.id,
                order_id=order_id,
                sequence=sequence
            )
            db.add(route_order)

        db_route.updated_at = datetime.utcnow()
        db.commit()

    return get_route(db_route.id, db)


@router.get("/", response_model=List[RouteModel])
def get_routes(
    driver_id: Optional[int] = None,
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Get all routes with optional filters, including order counts"""
    query = db.query(
        Route,
        func.count(RouteOrder.id).label('order_count')
    ).outerjoin(RouteOrder, Route.id == RouteOrder.route_id)

    if driver_id:
        query = query.filter(Route.driver_id == driver_id)
    if status:
        query = query.filter(Route.status == status)

    query = query.group_by(Route.id).offset(skip).limit(limit)

    # Convert to list of route dicts with order counts
    results = query.all()
    routes = []
    for route, order_count in results:
        route_dict = {
            "id": route.id,
            "driver_id": route.driver_id,
            "name": route.name,
            "date": route.date,
            "status": route.status,
            "created_at": route.created_at,
            "updated_at": route.updated_at,
            "order_count": order_count or 0
        }
        routes.append(route_dict)

    return routes


@router.get("/{route_id}", response_model=RouteWithOrders)
def get_route(route_id: int, db: Session = Depends(get_db)):
    """Get a specific route with its orders"""
    route = db.query(Route).filter(Route.id == route_id).first()
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")

    route_orders = db.query(RouteOrder).filter(RouteOrder.route_id == route_id)\
        .order_by(RouteOrder.sequence).all()

    # Convert route to dict, excluding SQLAlchemy internal attributes
    route_dict = {
        "id": route.id,
        "driver_id": route.driver_id,
        "name": route.name,
        "date": route.date,
        "status": route.status,
        "created_at": route.created_at,
        "updated_at": route.updated_at,
        "route_orders": []
    }

    # Convert route orders and orders to serializable dicts
    for ro in route_orders:
        order = db.query(Order).filter(Order.id == ro.order_id).first() if ro.order_id else None

        route_order_dict = {
            "id": ro.id,
            "order_id": ro.order_id,
            "sequence": ro.sequence,
            "status": ro.status,
            "estimated_arrival": ro.estimated_arrival,
            "actual_arrival": ro.actual_arrival,
        }

        # Add order data if available
        if order:
            route_order_dict["order"] = {
                "id": order.id,
                "order_number": order.order_number,
                "customer_name": order.customer_name,
                "customer_phone": order.customer_phone,
                "customer_email": order.customer_email,
                "delivery_address": order.delivery_address,
                "description": order.description,
                "latitude": order.latitude,
                "longitude": order.longitude,
                "items": order.items,
                "delivery_time_window_start": order.delivery_time_window_start,
                "delivery_time_window_end": order.delivery_time_window_end,
                "priority": order.priority,
                "status": order.status,
                "driver_status": order.driver_status,
                "assigned_driver_id": order.assigned_driver_id,
                "driver_notes": order.driver_notes,
                "failure_reason": order.failure_reason,
                "driver_status_updated_at": order.driver_status_updated_at,
                "driver_gps_lat": order.driver_gps_lat,
                "driver_gps_lng": order.driver_gps_lng,
                "delivered_at": order.delivered_at,
                "failed_at": order.failed_at,
                "proof_photo_path": order.proof_photo_path,
                "proof_signature_path": order.proof_signature_path,
                "proof_metadata": order.proof_metadata,
                "proof_captured_at": order.proof_captured_at,
                "source": order.source,
                "created_at": order.created_at,
                "updated_at": order.updated_at
            }
        else:
            route_order_dict["order"] = None

        route_dict["route_orders"].append(route_order_dict)

    return route_dict


@router.put("/{route_id}", response_model=RouteModel)
def update_route(route_id: int, route_update: RouteUpdate, db: Session = Depends(get_db)):
    """Update a route"""
    db_route = db.query(Route).filter(Route.id == route_id).first()
    if not db_route:
        raise HTTPException(status_code=404, detail="Route not found")

    update_data = route_update.dict(exclude_unset=True)
    previous_driver_id = db_route.driver_id
    new_driver_id = update_data.get("driver_id")

    # Verify driver exists if updating driver_id
    if new_driver_id is not None:
        driver = db.query(Driver).filter(Driver.id == new_driver_id).first()
        if not driver:
            raise HTTPException(status_code=404, detail="Driver not found")

    for field, value in update_data.items():
        setattr(db_route, field, value)

    db_route.updated_at = datetime.utcnow()

    if new_driver_id is not None and new_driver_id != previous_driver_id:
        route_orders = db.query(RouteOrder).filter(RouteOrder.route_id == route_id).all()
        for route_order in route_orders:
            if route_order.order:
                route_order.order.assigned_driver_id = new_driver_id
                route_order.order.driver_status = route_order.order.driver_status or "assigned"
                route_order.order.driver_status_updated_at = datetime.utcnow()

    db.commit()
    db.refresh(db_route)
    return db_route


@router.delete("/{route_id}")
def delete_route(route_id: int, db: Session = Depends(get_db)):
    """Delete a route"""
    db_route = db.query(Route).filter(Route.id == route_id).first()
    if not db_route:
        raise HTTPException(status_code=404, detail="Route not found")

    db.delete(db_route)
    db.commit()
    return {"message": "Route deleted successfully"}


@router.post("/{route_id}/orders", response_model=RouteWithOrders)
def add_orders_to_route(
    route_id: int,
    order_items: List[RouteOrderItem],
    db: Session = Depends(get_db)
):
    """Add orders to a route"""
    route = db.query(Route).filter(Route.id == route_id).first()
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")

    # Clear existing route orders
    db.query(RouteOrder).filter(RouteOrder.route_id == route_id).delete()

    # Add new route orders
    for item in order_items:
        # Verify order exists
        order = db.query(Order).filter(Order.id == item.order_id).first()
        if not order:
            raise HTTPException(status_code=404, detail=f"Order {item.order_id} not found")

        order.assigned_driver_id = route.driver_id
        order.driver_status = order.driver_status or "assigned"
        order.driver_status_updated_at = datetime.utcnow()
        order.status = "assigned"

        route_order = RouteOrder(
            route_id=route_id,
            order_id=item.order_id,
            sequence=item.sequence
        )
        db.add(route_order)

    route.updated_at = datetime.utcnow()
    db.commit()

    # Return updated route
    return get_route(route_id, db)


@router.post("/{route_id}/optimize")
def optimize_route_orders(
    route_id: int,
    db: Session = Depends(get_db)
):
    """Optimize the order sequence in a route considering depots, parking spots, and deliveries"""
    route = db.query(Route).filter(Route.id == route_id).first()
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")

    # Get route orders
    route_orders = db.query(RouteOrder).filter(RouteOrder.route_id == route_id)\
        .order_by(RouteOrder.sequence).all()

    if not route_orders:
        raise HTTPException(status_code=400, detail="Route has no orders to optimize")

    # Get depot (use first depot or driver's current location)
    depot = db.query(Depot).first()
    if not depot:
        # Use driver's current location or default
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
                detail="No depot found and driver has no location. Please create a depot or set driver location."
            )
    else:
        if not depot.latitude or not depot.longitude:
            raise HTTPException(
                status_code=400,
                detail=f"Depot '{depot.name}' is missing coordinates. Please update the depot with valid latitude and longitude."
            )
        depot_dict = {
            "id": depot.id,
            "name": depot.name,
            "latitude": depot.latitude,
            "longitude": depot.longitude
        }

    # Get order locations first (needed for parking data loading)
    orders_data = []
    for ro in route_orders:
        order = db.query(Order).filter(Order.id == ro.order_id).first()
        if order and order.latitude and order.longitude:
            orders_data.append({
                "id": order.id,
                "order_number": order.order_number,
                "latitude": order.latitude,
                "longitude": order.longitude,
                "delivery_address": order.delivery_address,
                "order": order
            })

    # Load OSM-derived parking locations near depot/orders (seeded via Overpass import)
    parking_data = _load_relevant_parking_locations(db, depot_dict, orders_data)

    if not orders_data:
        missing_orders = []
        for ro in route_orders:
            order = db.query(Order).filter(Order.id == ro.order_id).first()
            if not order:
                missing_orders.append(f"Order ID {ro.order_id} not found")
            elif not order.latitude or not order.longitude:
                missing_orders.append(f"Order {order.order_number or order.id} ({order.delivery_address}) missing coordinates")

        error_msg = "Orders missing location data. "
        if missing_orders:
            error_msg += "Issues: " + "; ".join(missing_orders[:3])
            if len(missing_orders) > 3:
                error_msg += f" (and {len(missing_orders) - 3} more)"
        else:
            error_msg += "Please ensure all orders have valid latitude and longitude coordinates."

        raise HTTPException(status_code=400, detail=error_msg)

    # Prepare data for optimization
    depot_coords = {
        "lat": depot_dict["latitude"],
        "lon": depot_dict["longitude"]
    }
    order_locations = [{"lat": o["latitude"], "lon": o["longitude"]} for o in orders_data]

    # Optimize route order (considering parking spots)
    optimized_indices = optimize_route(depot_coords, order_locations, parking_data)

    # Calculate complete route with parking spots
    # Uses dynamic parking by default (via find_nearest_parking with use_dynamic_parking=True)
    # Static parking_data is only used as fallback if OSRM is unavailable
    try:
        complete_route = calculate_complete_route(
            depot=depot_dict,
            orders=orders_data,
            parking_locations=parking_data,  # Can be empty list - dynamic parking will be used
            optimized_order_indices=optimized_indices,
            start_time=datetime.utcnow()
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error calculating route: {str(e)}")

    # Update route order sequences
    for new_seq, orig_idx in enumerate(optimized_indices, start=1):
        route_order = route_orders[orig_idx]
        route_order.sequence = new_seq

    route.updated_at = datetime.utcnow()
    db.commit()

    # Calculate optimization metrics
    original_order = list(range(len(orders_data)))
    improvement_metrics = calculate_route_improvement(
        original_order, optimized_indices, depot_dict, orders_data
    )

    return {
        "message": "Route optimized successfully",
        "optimized_order_ids": [orders_data[idx]["id"] for idx in optimized_indices],
        "optimization_metrics": improvement_metrics,
        "route_summary": {
            "total_distance_km": complete_route["total_distance_km"],
            "total_time_minutes": complete_route["total_time_minutes"],
            "waypoint_count": len(complete_route["waypoints"])
        },
        "waypoints": complete_route["waypoints"]
    }


@router.delete("/{route_id}/orders/{order_id}")
def remove_order_from_route(
    route_id: int,
    order_id: int,
    db: Session = Depends(get_db)
):
    """Remove an order from a route"""
    route_order = db.query(RouteOrder).filter(
        RouteOrder.route_id == route_id,
        RouteOrder.order_id == order_id
    ).first()

    if not route_order:
        raise HTTPException(status_code=404, detail="Order not found in route")

    order = db.query(Order).filter(Order.id == order_id).first()
    db.delete(route_order)

    if order:
        remaining_assignment = (
            db.query(RouteOrder)
            .filter(RouteOrder.order_id == order_id)
            .count()
        )
        if remaining_assignment == 0:
            order.assigned_driver_id = None
            order.driver_status = "unassigned"
            order.driver_status_updated_at = datetime.utcnow()

    db.commit()
    return {"message": "Order removed from route successfully"}


@router.post("/{route_id}/orders/create", response_model=RouteWithOrders)
def create_order_and_add_to_route(
    route_id: int,
    order: OrderCreate,
    db: Session = Depends(get_db)
):
    """
    Create a new order and add it to a route in one call.
    Handles geocoding if coordinates are not provided.
    """
    # Verify route exists
    route = db.query(Route).filter(Route.id == route_id).first()
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")

    db_order = prepare_order_for_db(order, db)
    db.add(db_order)
    db.flush()  # Flush to get the order ID

    # Get current max sequence number for this route
    max_sequence = db.query(RouteOrder).filter(
        RouteOrder.route_id == route_id
    ).order_by(RouteOrder.sequence.desc()).first()

    next_sequence = (max_sequence.sequence + 1) if max_sequence else 1

    # Add order to route
    route_order = RouteOrder(
        route_id=route_id,
        order_id=db_order.id,
        sequence=next_sequence
    )
    db.add(route_order)

    db_order.assigned_driver_id = route.driver_id
    db_order.driver_status = "assigned"
    db_order.driver_status_updated_at = datetime.utcnow()
    db_order.status = "assigned"

    route.updated_at = datetime.utcnow()
    db.commit()

    # Return updated route
    return get_route(route_id, db)


@router.get("/{route_id}/visualize")
def get_route_visualization(
    route_id: int,
    db: Session = Depends(get_db)
):
    """
    Get route data formatted for map visualization
    Returns route with waypoints, segments, and color coding
    """
    route = db.query(Route).filter(Route.id == route_id).first()
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")

    # Get route orders
    route_orders = db.query(RouteOrder).filter(RouteOrder.route_id == route_id)\
        .order_by(RouteOrder.sequence).all()

    if not route_orders:
        raise HTTPException(status_code=400, detail="Route has no orders")

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
                detail="No depot found and driver has no location. Please create a depot or set driver location."
            )
    else:
        if not depot.latitude or not depot.longitude:
            raise HTTPException(
                status_code=400,
                detail=f"Depot '{depot.name}' is missing coordinates. Please update the depot with valid latitude and longitude."
            )
        depot_dict = {
            "id": depot.id,
            "name": depot.name,
            "latitude": depot.latitude,
            "longitude": depot.longitude
        }

    # Get order locations first (needed for parking data loading)
    orders_data = []
    for ro in route_orders:
        order = db.query(Order).filter(Order.id == ro.order_id).first()
        if order and order.latitude and order.longitude:
            orders_data.append({
                "id": order.id,
                "order_number": order.order_number,
                "latitude": order.latitude,
                "longitude": order.longitude,
                "delivery_address": order.delivery_address,
                "customer_name": order.customer_name,
                "order": order
            })

    # Load nearby parking points that were generated from the Overpass dataset
    parking_data = _load_relevant_parking_locations(db, depot_dict, orders_data)

    if not orders_data:
        missing_orders = []
        for ro in route_orders:
            order = db.query(Order).filter(Order.id == ro.order_id).first()
            if not order:
                missing_orders.append(f"Order ID {ro.order_id} not found")
            elif not order.latitude or not order.longitude:
                missing_orders.append(f"Order {order.order_number or order.id} ({order.delivery_address}) missing coordinates")

        error_msg = "Orders missing location data. "
        if missing_orders:
            error_msg += "Issues: " + "; ".join(missing_orders[:3])
            if len(missing_orders) > 3:
                error_msg += f" (and {len(missing_orders) - 3} more)"
        else:
            error_msg += "Please ensure all orders have valid latitude and longitude coordinates."

        raise HTTPException(status_code=400, detail=error_msg)

    # Get current order sequence
    order_locations = [{"lat": o["latitude"], "lon": o["longitude"]} for o in orders_data]
    current_sequence = [i for i in range(len(orders_data))]

    # Calculate complete route
    # Uses dynamic parking by default (via find_nearest_parking with use_dynamic_parking=True)
    # Static parking_data is only used as fallback if OSRM is unavailable
    try:
        complete_route = calculate_complete_route(
            depot=depot_dict,
            orders=orders_data,
            parking_locations=parking_data,  # Can be empty list - dynamic parking will be used
            optimized_order_indices=current_sequence,
            start_time=datetime.utcnow()
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error calculating route: {str(e)}")

    # Format waypoints for visualization
    waypoints = []
    segments = []

    for i, waypoint in enumerate(complete_route["waypoints"]):
        # Determine color based on type
        if waypoint["type"] == "depot":
            color = "#FF0000"  # Red for depot
            icon = "warehouse"
        elif waypoint["type"] == "parking":
            color = "#FFA500"  # Orange for parking
            icon = "parking"
        else:  # delivery
            color = "#008000"  # Green for delivery
            icon = "delivery"

        waypoints.append({
            "id": i,
            "type": waypoint["type"],
            "lat": waypoint["lat"],
            "lng": waypoint["lon"],
            "color": color,
            "icon": icon,
            "metadata": waypoint.get("metadata", {}),
            "estimated_arrival": waypoint.get("estimated_arrival"),
            "sequence": i
        })

        # Create segment to next waypoint
        if i < len(complete_route["waypoints"]) - 1:
            next_waypoint = complete_route["waypoints"][i + 1]
            segments.append({
                "from": {
                    "lat": waypoint["lat"],
                    "lng": waypoint["lon"]
                },
                "to": {
                    "lat": next_waypoint["lat"],
                    "lng": next_waypoint["lon"]
                },
                "color": color,
                "sequence": i
            })

    result = {
        "route_id": route_id,
        "route_name": route.name,
        "driver_id": route.driver_id,
        "status": route.status,
        "waypoints": waypoints,
        "segments": segments,
        "summary": {
            "total_distance_km": complete_route["total_distance_km"],
            "total_time_minutes": complete_route["total_time_minutes"],
            "waypoint_count": len(waypoints),
            "delivery_count": len([w for w in waypoints if w["type"] == "delivery"])
        },
        "colors": {
            "depot": "#FF0000",
            "parking": "#FFA500",
            "delivery": "#008000"
        }
    }

    # Add route geometry if available (from OSRM)
    if complete_route.get("geometry"):
        result["geometry"] = complete_route["geometry"]  # GeoJSON LineString

    return result


@router.get("/driver/{driver_id}/google-maps-url")
def get_google_maps_url_for_driver(
    driver_id: int,
    db: Session = Depends(get_db)
):
    """
    Generate a Google Maps URL with all waypoints (depot, deliveries, parking) for a driver's active route.
    Returns a URL that opens Google Maps with the full itinerary.
    """
    import urllib.parse

    # Get the driver's active route
    route = db.query(Route).filter(
        Route.driver_id == driver_id,
        Route.status.in_(["active", "in_progress", "assigned"])
    ).order_by(Route.created_at.desc()).first()

    if not route:
        # Try to get any route for the driver
        route = db.query(Route).filter(Route.driver_id == driver_id).order_by(Route.created_at.desc()).first()

    if not route:
        raise HTTPException(status_code=404, detail="No route found for this driver")

    # Get route orders
    route_orders = db.query(RouteOrder).filter(RouteOrder.route_id == route.id)\
        .order_by(RouteOrder.sequence).all()

    if not route_orders:
        raise HTTPException(status_code=400, detail="Route has no orders")

    # Get depot
    depot = db.query(Depot).first()
    if not depot:
        driver = db.query(Driver).filter(Driver.id == driver_id).first()
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
                detail="No depot found and driver has no location."
            )
    else:
        if not depot.latitude or not depot.longitude:
            raise HTTPException(
                status_code=400,
                detail=f"Depot '{depot.name}' is missing coordinates."
            )
        depot_dict = {
            "id": depot.id,
            "name": depot.name,
            "address": depot.address,  # Include address for Google Maps
            "latitude": depot.latitude,
            "longitude": depot.longitude
        }

    # Get order locations with addresses
    orders_data = []
    for ro in route_orders:
        order = db.query(Order).filter(Order.id == ro.order_id).first()
        if order and order.latitude and order.longitude:
            orders_data.append({
                "id": order.id,
                "latitude": order.latitude,
                "longitude": order.longitude,
                "delivery_address": order.delivery_address,  # Include address for Google Maps
            })

    if not orders_data:
        raise HTTPException(status_code=400, detail="Orders missing location data")

    # Load parking locations
    parking_data = _load_relevant_parking_locations(db, depot_dict, orders_data)

    # Calculate complete route with parking
    order_locations = [{"lat": o["latitude"], "lon": o["longitude"]} for o in orders_data]
    current_sequence = [i for i in range(len(orders_data))]

    try:
        complete_route = calculate_complete_route(
            depot=depot_dict,
            orders=orders_data,
            parking_locations=parking_data,
            optimized_order_indices=current_sequence,
            start_time=datetime.utcnow()
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error calculating route: {str(e)}")

    # Extract coordinates from waypoints (depot, parking, deliveries in sequence)
    # Include all waypoints including parking spots so driver knows where to park
    waypoints = complete_route.get("waypoints", [])
    coords = []
    for wp in waypoints:
        if wp.get("lat") and wp.get("lon"):
            coords.append((wp["lat"], wp["lon"]))

    if len(coords) < 2:
        raise HTTPException(status_code=400, detail="Route needs at least 2 waypoints")

    # Build Google Maps URL
    # Format: https://www.google.com/maps/dir/?api=1&origin=LAT1,LON1&destination=LATn,LONn&waypoints=LAT2,LON2|LAT3,LON3|...
    origin = f"{coords[0][0]},{coords[0][1]}"
    destination = f"{coords[-1][0]},{coords[-1][1]}"

    # Google Maps supports up to ~23 waypoints, so we include all intermediate points
    # Skip first (origin) and last (destination) from waypoints
    waypoint_coords = coords[1:-1] if len(coords) > 2 else []

    # Limit to 20 waypoints to stay under Google's limit
    if len(waypoint_coords) > 20:
        # Sample every Nth point to reduce to 20
        step = len(waypoint_coords) // 20
        waypoint_coords = waypoint_coords[::step][:20]

    waypoints_str = "|".join([f"{lat},{lon}" for lat, lon in waypoint_coords])

    google_url = (
        "https://www.google.com/maps/dir/?api=1"
        f"&origin={urllib.parse.quote(origin)}"
        f"&destination={urllib.parse.quote(destination)}"
    )

    if waypoints_str:
        google_url += f"&waypoints={urllib.parse.quote(waypoints_str)}"

    return {
        "url": google_url,
        "waypoint_count": len(coords),
        "route_id": route.id,
        "route_name": route.name
    }


@router.post("/plan")
def plan_routes(
    plan_request: PlanRoutesRequest,
    db: Session = Depends(get_db)
):
    """
    Automatically plan routes using nearest-neighbor greedy approach

    Algorithm:
    1. Get all pending orders
    2. Find the shortest distance from depot to next delivery
    3. Find other deliveries close to that first delivery
    4. Assign up to 10 deliveries per driver
    5. Move to next driver for the next batch
    6. Update order status to 'assigned' and driver status to 'on_route'
    """
    import logging
    from ..services.route_calculator import calculate_distance
    from ..services.osrm_client import get_route_distance_and_time, check_osrm_available

    logger = logging.getLogger(__name__)

    # Get pending orders
    query = db.query(Order).filter(Order.status == "pending")

    # Filter by date if provided
    if plan_request.date:
        try:
            target_date = datetime.fromisoformat(plan_request.date.replace('Z', '+00:00'))
            query = query.filter(
                db.func.date(Order.created_at) == target_date.date()
            )
        except Exception as e:
            logger.warning(f"Failed to parse date filter: {e}")

    pending_orders = query.all()

    if not pending_orders:
        return {
            "routes": [],
            "statistics": {
                "total_routes": 0,
                "total_orders": 0,
                "total_distance_km": 0,
                "total_time_minutes": 0,
                "total_time_hours": 0,
                "drivers_used": 0,
                "unscheduled_orders": 0,
                "average_orders_per_route": 0,
                "average_distance_per_route": 0
            }
        }

    # Get depot
    depot = db.query(Depot).first()
    if not depot:
        raise HTTPException(status_code=400, detail="No depot configured")

    depot_lat = depot.latitude
    depot_lon = depot.longitude

    if not depot_lat or not depot_lon:
        raise HTTPException(status_code=400, detail="Depot location not configured")

    # Get drivers
    driver_query = db.query(Driver)
    if plan_request.driver_ids:
        driver_query = driver_query.filter(Driver.id.in_(plan_request.driver_ids))

    drivers = driver_query.all()
    if not drivers:
        raise HTTPException(status_code=400, detail="No drivers available")

    # Maximum orders per route
    max_orders_per_route = min(plan_request.max_orders_per_route or 10, 10)
    proximity_km = plan_request.max_distance_km or 5.0  # How close orders should be to each other

    # Track which orders are assigned
    unassigned_orders = [
        {
            "id": order.id,
            "order_number": order.order_number,
            "latitude": order.latitude,
            "longitude": order.longitude,
            "delivery_address": order.delivery_address,
            "db_order": order  # Keep reference to DB object for updates
        }
        for order in pending_orders
        if order.latitude and order.longitude
    ]

    # Use OSRM if available for more accurate distances
    use_osrm = check_osrm_available()

    created_routes = []
    driver_index = 0
    route_index = 0

    while unassigned_orders and driver_index < len(drivers):
        driver = drivers[driver_index]
        current_route_orders = []

        # Find the nearest order from depot (or last assigned order)
        current_lat = depot_lat
        current_lon = depot_lon

        while len(current_route_orders) < max_orders_per_route and unassigned_orders:
            # Find nearest unassigned order
            nearest_order = None
            nearest_distance = float('inf')

            for order in unassigned_orders:
                if not order["latitude"] or not order["longitude"]:
                    continue

                # Calculate distance
                if use_osrm:
                    try:
                        distance_km, _ = get_route_distance_and_time(
                            current_lat, current_lon,
                            order["latitude"], order["longitude"]
                        )
                        if distance_km is None:
                            # Fallback to Haversine
                            distance_km = calculate_distance(
                                current_lat, current_lon,
                                order["latitude"], order["longitude"]
                            )
                    except Exception as e:
                        logger.warning(f"OSRM distance calculation failed: {e}")
                        distance_km = calculate_distance(
                            current_lat, current_lon,
                            order["latitude"], order["longitude"]
                        )
                else:
                    distance_km = calculate_distance(
                        current_lat, current_lon,
                        order["latitude"], order["longitude"]
                    )

                if distance_km < nearest_distance:
                    nearest_distance = distance_km
                    nearest_order = order

            if not nearest_order:
                break

            # Add nearest order to route
            current_route_orders.append(nearest_order["id"])
            unassigned_orders.remove(nearest_order)

            # Now find orders close to this one
            current_lat = nearest_order["latitude"]
            current_lon = nearest_order["longitude"]

            # Find nearby orders (within proximity_km)
            nearby_orders = []
            for order in unassigned_orders:
                if not order["latitude"] or not order["longitude"]:
                    continue

                if use_osrm:
                    try:
                        distance_km, _ = get_route_distance_and_time(
                            current_lat, current_lon,
                            order["latitude"], order["longitude"]
                        )
                        if distance_km is None:
                            distance_km = calculate_distance(
                                current_lat, current_lon,
                                order["latitude"], order["longitude"]
                            )
                    except Exception:
                        distance_km = calculate_distance(
                            current_lat, current_lon,
                            order["latitude"], order["longitude"]
                        )
                else:
                    distance_km = calculate_distance(
                        current_lat, current_lon,
                        order["latitude"], order["longitude"]
                    )

                if distance_km <= proximity_km and len(current_route_orders) < max_orders_per_route:
                    nearby_orders.append((order, distance_km))

            # Sort nearby orders by distance and add them
            nearby_orders.sort(key=lambda x: x[1])
            for order, _ in nearby_orders[:max_orders_per_route - len(current_route_orders)]:
                current_route_orders.append(order["id"])
                unassigned_orders.remove(order)
                # Update current position for next iteration
                current_lat = order["latitude"]
                current_lon = order["longitude"]

        # Create route with these orders
        if current_route_orders:
            # Get order objects
            route_orders_db = [db.query(Order).filter(Order.id == oid).first() for oid in current_route_orders]
            route_orders_db = [o for o in route_orders_db if o]

            if route_orders_db:
                # Convert to dict format for optimization
                orders_for_opt = []
                for order in route_orders_db:
                    orders_for_opt.append({
                        "id": order.id,
                        "lat": order.latitude,
                        "lon": order.longitude,
                        "latitude": order.latitude,
                        "longitude": order.longitude
                    })

                depot_dict = {
                    "lat": depot_lat,
                    "lon": depot_lon,
                    "latitude": depot_lat,
                    "longitude": depot_lon
                }

                # Optimize route order using 2-opt
                try:
                    from ..services.route_optimizer import optimize_route_2opt
                    optimized_order_indices = optimize_route_2opt(
                        depot_dict,
                        orders_for_opt,
                        iterations=50
                    )
                    # Map indices back to order IDs
                    optimized_order_ids = [orders_for_opt[idx]["id"] for idx in optimized_order_indices]
                except Exception as e:
                    logger.warning(f"Route optimization failed, using original order: {e}")
                    optimized_order_ids = current_route_orders

                # Create route
                db_route = Route(
                    name=f"Route {route_index + 1}",
                    driver_id=driver.id,
                    status="planned",
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                db.add(db_route)
                db.flush()

                # Create a mapping of order_id to order object
                order_map = {order.id: order for order in route_orders_db}

                # Add orders to route in optimized order and update their status
                for seq, order_id in enumerate(optimized_order_ids):
                    order = order_map.get(order_id)
                    if not order:
                        continue

                    route_order = RouteOrder(
                        route_id=db_route.id,
                        order_id=order.id,
                        sequence=seq + 1
                    )
                    db.add(route_order)

                    # Update order status to assigned
                    order.status = "assigned"
                    order.assigned_driver_id = driver.id
                    order.updated_at = datetime.utcnow()

                # Update driver status to on_route
                driver.status = "on_route"

                db.commit()
                db.refresh(db_route)

                # Get route with orders for response
                created_routes.append({
                    "route_id": db_route.id,
                    "driver_id": driver.id,
                    "driver_name": driver.name,
                    "order_ids": optimized_order_ids,
                    "order_count": len(optimized_order_ids)
                })

                route_index += 1

        # Move to next driver
        driver_index += 1

    # Calculate statistics
    total_orders_assigned = sum(len(r["order_ids"]) for r in created_routes)
    total_orders = len(pending_orders)

    return {
        "routes": created_routes,
        "statistics": {
            "total_routes": len(created_routes),
            "total_orders": total_orders_assigned,
            "total_distance_km": 0,  # Could calculate if needed
            "total_time_minutes": 0,
            "total_time_hours": 0,
            "drivers_used": len(set(r["driver_id"] for r in created_routes)),
            "unscheduled_orders": total_orders - total_orders_assigned,
            "average_orders_per_route": round(total_orders_assigned / len(created_routes), 1) if created_routes else 0,
            "average_distance_per_route": 0
        }
    }
