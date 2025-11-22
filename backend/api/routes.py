from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from ..database import get_db, Route, RouteOrder, Order, Driver, Depot
from ..models import (
    RouteCreate, RouteUpdate, Route as RouteModel,
    RouteOrderItem, RouteWithOrders
)
from ..services.route_optimizer import optimize_route
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

    route_dict = {
        **route.__dict__,
        "route_orders": [
            {
                "id": ro.id,
                "order_id": ro.order_id,
                "sequence": ro.sequence,
                "status": ro.status,
                "estimated_arrival": ro.estimated_arrival,
                "actual_arrival": ro.actual_arrival,
                "order": db.query(Order).filter(Order.id == ro.order_id).first().__dict__ if ro.order_id else None
            }
            for ro in route_orders
        ]
    }

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
    """Optimize the order sequence in a route using AI"""
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
        if driver and driver.current_location_lat:
            depot_coords = {
                "lat": driver.current_location_lat,
                "lon": driver.current_location_lng
            }
        else:
            raise HTTPException(status_code=400, detail="No depot or driver location available")
    else:
        depot_coords = {
            "lat": depot.latitude,
            "lon": depot.longitude
        }

    # Get order locations
    orders_data = []
    for ro in route_orders:
        order = db.query(Order).filter(Order.id == ro.order_id).first()
        if order and order.latitude and order.longitude:
            orders_data.append({
                "id": order.id,
                "latitude": order.latitude,
                "longitude": order.longitude,
                "order": order
            })

    if not orders_data:
        raise HTTPException(status_code=400, detail="Orders missing location data")

    # Optimize route
    order_locations = [{"lat": o["latitude"], "lon": o["longitude"]} for o in orders_data]
    optimized_indices = optimize_route(depot_coords, order_locations)

    # Update route order sequences
    for new_seq, orig_idx in enumerate(optimized_indices, start=1):
        route_order = route_orders[orig_idx]
        route_order.sequence = new_seq

    route.updated_at = datetime.utcnow()
    db.commit()

    return {
        "message": "Route optimized successfully",
        "optimized_order_ids": [orders_data[idx]["id"] for idx in optimized_indices]
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
