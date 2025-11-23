#!/usr/bin/env python3
"""
Add test orders with valid coordinates for video demo.
These orders are pre-geocoded and ready for route planning.
"""

import sys
import os
from datetime import datetime, timedelta, timezone

# Add parent directory to path
project_root = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, os.path.abspath(project_root))

try:
    from backend.database import SessionLocal, Order
except ImportError as e:
    print(f"Error importing backend modules: {e}")
    sys.exit(1)

# Pre-geocoded orders in Heilbronn area (near the depot)
TEST_ORDERS = [
    {
        "order_number": "DEMO-001",
        "customer_name": "Max Mustermann",
        "customer_phone": "+49 7131 123456",
        "customer_email": "max@example.de",
        "delivery_address": "Kiliansplatz 1, 74072 Heilbronn, Germany",
        "latitude": 49.1437,
        "longitude": 9.2109,
        "description": "Office supplies",
        "priority": "normal",
        "source": "email",
        "items": [{"name": "Product A", "quantity": 2}]
    },
    {
        "order_number": "DEMO-002",
        "customer_name": "Anna Schmidt",
        "customer_phone": "+49 7131 234567",
        "customer_email": "anna@example.de",
        "delivery_address": "Allee 12, 74076 Heilbronn, Germany",
        "latitude": 49.1395,
        "longitude": 9.2067,
        "description": "Urgent delivery",
        "priority": "high",
        "source": "phone",
        "items": [{"name": "Product B", "quantity": 1}]
    },
    {
        "order_number": "DEMO-003",
        "customer_name": "Thomas Weber",
        "customer_phone": "+49 7131 345678",
        "customer_email": "thomas@example.de",
        "delivery_address": "Crailsheimstraße 45, 74074 Heilbronn, Germany",
        "latitude": 49.1478,
        "longitude": 9.2156,
        "description": "Regular delivery",
        "priority": "normal",
        "source": "email",
        "items": [{"name": "Product C", "quantity": 3}]
    },
    {
        "order_number": "DEMO-004",
        "customer_name": "Lisa Fischer",
        "customer_phone": "+49 7131 456789",
        "customer_email": "lisa@example.de",
        "delivery_address": "Willy-Brandt-Platz 2, 74072 Heilbronn, Germany",
        "latitude": 49.1423,
        "longitude": 9.2101,
        "description": "Express delivery",
        "priority": "urgent",
        "source": "phone",
        "items": [{"name": "Product D", "quantity": 1}]
    },
    {
        "order_number": "DEMO-005",
        "customer_name": "Peter Müller",
        "customer_phone": "+49 7131 567890",
        "customer_email": "peter@example.de",
        "delivery_address": "Kaiserstraße 78, 74072 Heilbronn, Germany",
        "latitude": 49.1412,
        "longitude": 9.2089,
        "description": "Standard delivery",
        "priority": "normal",
        "source": "email",
        "items": [{"name": "Product E", "quantity": 2}]
    },
    {
        "order_number": "DEMO-006",
        "customer_name": "Sarah Klein",
        "customer_phone": "+49 7131 678901",
        "customer_email": "sarah@example.de",
        "delivery_address": "Sülmerstraße 7, 74072 Heilbronn, Germany",
        "latitude": 49.1427,
        "longitude": 9.2186,
        "description": "Regular order",
        "priority": "normal",
        "source": "fax",
        "items": [{"name": "Product F", "quantity": 4}]
    },
    {
        "order_number": "DEMO-007",
        "customer_name": "David Wagner",
        "customer_phone": "+49 7131 789012",
        "customer_email": "david@example.de",
        "delivery_address": "Kaiserstraße 23, 74072 Heilbronn, Germany",
        "latitude": 49.1413,
        "longitude": 9.2195,
        "description": "Priority shipment",
        "priority": "high",
        "source": "email",
        "items": [{"name": "Product G", "quantity": 1}]
    },
    {
        "order_number": "DEMO-008",
        "customer_name": "Julia Becker",
        "customer_phone": "+49 7131 890123",
        "customer_email": "julia@example.de",
        "delivery_address": "Allee 19, 74072 Heilbronn, Germany",
        "latitude": 49.1405,
        "longitude": 9.2206,
        "description": "Standard delivery",
        "priority": "normal",
        "source": "phone",
        "items": [{"name": "Product H", "quantity": 2}]
    },
    {
        "order_number": "DEMO-009",
        "customer_name": "Markus Huber",
        "customer_phone": "+49 7131 901234",
        "customer_email": "markus@example.de",
        "delivery_address": "Fleiner Straße 8, 74072 Heilbronn, Germany",
        "latitude": 49.1390,
        "longitude": 9.2243,
        "description": "Express order",
        "priority": "urgent",
        "source": "email",
        "items": [{"name": "Product I", "quantity": 1}]
    },
    {
        "order_number": "DEMO-010",
        "customer_name": "Sophie Richter",
        "customer_phone": "+49 7131 012345",
        "customer_email": "sophie@example.de",
        "delivery_address": "Karlstraße 18, 74072 Heilbronn, Germany",
        "latitude": 49.1384,
        "longitude": 9.2203,
        "description": "Regular shipment",
        "priority": "normal",
        "source": "fax",
        "items": [{"name": "Product J", "quantity": 3}]
    },
]

def add_test_orders():
    """Add test orders with valid coordinates"""
    db = SessionLocal()
    try:
        created = 0

        for order_data in TEST_ORDERS:
            # Check if order already exists
            existing = db.query(Order).filter(Order.order_number == order_data["order_number"]).first()
            if existing:
                # Update existing order to pending with coordinates
                existing.status = "pending"
                existing.latitude = order_data["latitude"]
                existing.longitude = order_data["longitude"]
                existing.delivery_address = order_data["delivery_address"]
                existing.assigned_driver_id = None
                existing.driver_status = "unassigned"
                existing.updated_at = datetime.now(timezone.utc)
                print(f"✅ Updated order {existing.id}: {order_data['order_number']}")
            else:
                # Create new order
                order = Order(
                    order_number=order_data["order_number"],
                    customer_name=order_data["customer_name"],
                    customer_phone=order_data["customer_phone"],
                    customer_email=order_data["customer_email"],
                    delivery_address=order_data["delivery_address"],
                    latitude=order_data["latitude"],
                    longitude=order_data["longitude"],
                    description=order_data["description"],
                    priority=order_data["priority"],
                    status="pending",
                    driver_status="unassigned",
                    source=order_data["source"],
                    items=order_data["items"],
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc)
                )
                db.add(order)
                created += 1
                print(f"✅ Created order: {order_data['order_number']}")

        db.commit()

        # Count pending orders with coordinates
        count = db.query(Order).filter(
            Order.status == "pending",
            Order.latitude != None,
            Order.longitude != None
        ).count()

        print(f"\n✅ Added/updated {len(TEST_ORDERS)} test orders")
        print(f"📊 Total pending orders with coordinates: {count}")
        print("\n✨ Ready for route planning! Click 'Plan Routes' in the UI.")

    except Exception as e:
        db.rollback()
        print(f"❌ Error adding test orders: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    print("Adding test orders for video demo...")
    add_test_orders()
