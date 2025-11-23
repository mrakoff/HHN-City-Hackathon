#!/usr/bin/env python3
"""
Quick script to reset all orders to pending status for video recording.
This will:
1. Set all orders to "pending" status
2. Clear assigned_driver_id
3. Reset driver_status to "unassigned"
4. Delete all route_orders (so orders can be assigned to new routes)
5. Reset routes to "planned" status

Run: python3 scripts/reset_orders_to_pending.py
"""

import sys
import os
from datetime import datetime

# Add parent directory to path
project_root = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, os.path.abspath(project_root))

try:
    from backend.database import SessionLocal, Order, Route, RouteOrder
except ImportError as e:
    print(f"Error importing backend modules: {e}")
    sys.exit(1)

def reset_orders_to_pending():
    """Reset all orders to pending and clear route assignments"""
    db = SessionLocal()
    try:
        # Get all orders
        orders = db.query(Order).all()
        order_count = len(orders)

        # Reset each order
        for order in orders:
            order.status = "pending"
            order.assigned_driver_id = None
            order.driver_status = "unassigned"
            order.driver_status_updated_at = None
            order.driver_notes = None
            order.failure_reason = None
            order.delivered_at = None
            order.failed_at = None
            order.updated_at = datetime.utcnow()

        # Delete all route_orders (this unlinks orders from routes)
        route_orders_deleted = db.query(RouteOrder).delete()

        # Reset all routes to "planned" status
        routes = db.query(Route).all()
        for route in routes:
            route.status = "planned"
            route.updated_at = datetime.utcnow()

        db.commit()

        print(f"✅ Reset {order_count} orders to pending status")
        print(f"✅ Deleted {route_orders_deleted} route_order assignments")
        print(f"✅ Reset {len(routes)} routes to 'planned' status")
        print("\n✨ All orders are now ready for new route creation!")

    except Exception as e:
        db.rollback()
        print(f"❌ Error resetting orders: {e}")
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    print("Resetting all orders to pending status...")
    reset_orders_to_pending()
