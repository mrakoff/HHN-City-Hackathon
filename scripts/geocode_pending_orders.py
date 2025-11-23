#!/usr/bin/env python3
"""
Geocode all pending orders that have addresses but no coordinates.
This will enable route planning to work.
"""

import sys
import os
from datetime import datetime

# Add parent directory to path
project_root = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, os.path.abspath(project_root))

try:
    from backend.database import SessionLocal, Order
    from backend.services.geocoding import geocode_address
except ImportError as e:
    print(f"Error importing backend modules: {e}")
    sys.exit(1)

def geocode_pending_orders():
    """Geocode all pending orders without coordinates"""
    db = SessionLocal()
    try:
        # Get pending orders without coordinates but with addresses
        orders = db.query(Order).filter(
            Order.status == "pending",
            (Order.latitude == None) | (Order.longitude == None),
            Order.delivery_address != None,
            Order.delivery_address != ""
        ).all()

        print(f"Found {len(orders)} orders to geocode...")

        geocoded = 0
        failed = 0

        for order in orders:
            if not order.delivery_address or order.delivery_address.strip() == "":
                continue

            print(f"Geocoding order {order.id}: {order.delivery_address[:50]}...")

            # Try geocoding
            coords = geocode_address(order.delivery_address)

            if coords:
                order.latitude = coords['lat']
                order.longitude = coords['lon']
                order.updated_at = datetime.utcnow()
                geocoded += 1
                print(f"  ✅ Success: {coords['lat']:.6f}, {coords['lon']:.6f}")
            else:
                failed += 1
                print(f"  ❌ Failed to geocode")
                # Try appending city if not present
                if "Heilbronn" not in order.delivery_address and "Stuttgart" not in order.delivery_address:
                    address_with_city = f"{order.delivery_address}, Heilbronn, Germany"
                    print(f"  Retrying with city: {address_with_city[:50]}...")
                    coords = geocode_address(address_with_city)
                    if coords:
                        order.latitude = coords['lat']
                        order.longitude = coords['lon']
                        order.updated_at = datetime.utcnow()
                        geocoded += 1
                        failed -= 1
                        print(f"  ✅ Success with city: {coords['lat']:.6f}, {coords['lon']:.6f}")

        db.commit()

        print(f"\n✅ Geocoded {geocoded} orders")
        if failed > 0:
            print(f"⚠️  {failed} orders could not be geocoded")

        # Check final count
        orders_with_coords = db.query(Order).filter(
            Order.status == "pending",
            Order.latitude != None,
            Order.longitude != None
        ).count()

        print(f"\n📊 Total pending orders with coordinates: {orders_with_coords}")
        print("\n✨ Orders are now ready for route planning!")

    except Exception as e:
        db.rollback()
        print(f"❌ Error geocoding orders: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    print("Geocoding pending orders...")
    geocode_pending_orders()
