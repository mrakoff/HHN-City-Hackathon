from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from ..database import get_db, Route, RouteOrder, Order, Driver, Depot, ParkingLocation
from ..models import (
    RouteCreate, RouteUpdate, Route as RouteModel,
    RouteOrderItem, RouteWithOrders
)
from ..services.route_optimizer import optimize_route
from ..services.route_calculator import calculate_complete_route
from ..services.ai_agents import suggest_route_optimization

router = APIRouter(prefix="/api/routes", tags=["routes"])


@router.post("/", response_model=RouteModel)
def create_route(route: RouteCreate, db: Session = Depends(get_db)):
    """Create a new route"""
    # Verify driver exists
    driver = db.query(Driver).filter(Driver.id == route.driver_id).first()
    if not driver:
        raise HTTPException(status_code=404, detail="Driver not found")

    db_route = Route(**route.dict())
    db.add(db_route)
    db.commit()
    db.refresh(db_route)
    return db_route


@router.get("/", response_model=List[RouteModel])
def get_routes(
    driver_id: Optional[int] = None,
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Get all routes with optional filters"""
    query = db.query(Route)

    if driver_id:
        query = query.filter(Route.driver_id == driver_id)
    if status:
        query = query.filter(Route.status == status)

    routes = query.offset(skip).limit(limit).all()
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

    # Verify driver exists if updating driver_id
    if "driver_id" in update_data:
        driver = db.query(Driver).filter(Driver.id == update_data["driver_id"]).first()
        if not driver:
            raise HTTPException(status_code=404, detail="Driver not found")

    for field, value in update_data.items():
        setattr(db_route, field, value)

    db_route.updated_at = datetime.utcnow()
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

    # Get parking locations
    parking_locations = db.query(ParkingLocation).all()
    parking_data = [
        {
            "id": p.id,
            "name": p.name,
            "latitude": p.latitude,
            "longitude": p.longitude,
            "address": p.address
        }
        for p in parking_locations
        if p.latitude and p.longitude
    ]

    # Get order locations
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
    try:
        complete_route = calculate_complete_route(
            depot=depot_dict,
            orders=orders_data,
            parking_locations=parking_data,
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

    return {
        "message": "Route optimized successfully",
        "optimized_order_ids": [orders_data[idx]["id"] for idx in optimized_indices],
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

    db.delete(route_order)
    db.commit()
    return {"message": "Order removed from route successfully"}


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

    # Get parking locations
    parking_locations = db.query(ParkingLocation).all()
    parking_data = [
        {
            "id": p.id,
            "name": p.name,
            "latitude": p.latitude,
            "longitude": p.longitude,
            "address": p.address
        }
        for p in parking_locations
        if p.latitude and p.longitude
    ]

    # Get order locations
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
