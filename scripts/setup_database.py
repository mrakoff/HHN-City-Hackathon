#!/usr/bin/env python3
"""
Setup script to populate the database with sample data for routing.
Creates drivers, depots, parking locations, and sample orders.
Run this from the project root directory with: python3 scripts/setup_database.py
"""

import sys
import os
from datetime import datetime, timedelta

# Add parent directory to path to import backend modules
project_root = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, os.path.abspath(project_root))

try:
    from backend.database import SessionLocal, Driver, Depot, ParkingLocation, Order
except ImportError as e:
    print(f"Error importing backend modules: {e}")
    print("Make sure you're running this from the project root and dependencies are installed.")
    print("Try: pip install -r requirements.txt")
    sys.exit(1)

# Sample data - Baden-Württemberg area coordinates (Stuttgart region)
# All coordinates are within the OSRM coverage area
DRIVERS = [
    {
        "name": "Michael Schneider",
        "phone": "+49 711 11111111",
        "email": "michael.schneider@delivery.com",
        "status": "available"
    },
    {
        "name": "Anna Weber",
        "phone": "+49 711 22222222",
        "email": "anna.weber@delivery.com",
        "status": "available"
    },
    {
        "name": "Thomas Fischer",
        "phone": "+49 711 33333333",
        "email": "thomas.fischer@delivery.com",
        "status": "available"
    },
    {
        "name": "Lisa Müller",
        "phone": "+49 711 44444444",
        "email": "lisa.mueller@delivery.com",
        "status": "available"
    },
    {
        "name": "David Schmidt",
        "phone": "+49 711 55555555",
        "email": "david.schmidt@delivery.com",
        "status": "available"
    }
]

DEPOTS = [
    {
        "name": "Main Depot Stuttgart",
        "address": "Hauptbahnhof 1, 70173 Stuttgart, Germany",
        "latitude": 48.7833,
        "longitude": 9.1817
    }
]

PARKING_LOCATIONS = [
    {
        "name": "Parking Königstraße",
        "address": "Königstraße 50, 70173 Stuttgart, Germany",
        "latitude": 48.7784,
        "longitude": 9.1829,
        "notes": "Near Königstraße shopping area"
    },
    {
        "name": "Parking Schlossplatz",
        "address": "Schlossplatz 1, 70173 Stuttgart, Germany",
        "latitude": 48.7784,
        "longitude": 9.1829,
        "notes": "Central Stuttgart parking"
    },
    {
        "name": "Parking Marienplatz",
        "address": "Marienplatz 1, 70178 Stuttgart, Germany",
        "latitude": 48.7758,
        "longitude": 9.1829,
        "notes": "Near Marienplatz"
    },
    {
        "name": "Parking Rotebühlplatz",
        "address": "Rotebühlplatz 1, 70178 Stuttgart, Germany",
        "latitude": 48.7744,
        "longitude": 9.1708,
        "notes": "Near Rotebühlplatz"
    },
    {
        "name": "Parking Feuersee",
        "address": "Feuerseeplatz 1, 70178 Stuttgart, Germany",
        "latitude": 48.7700,
        "longitude": 9.1700,
        "notes": "Near Feuersee area"
    },
    {
        "name": "Parking Bad Cannstatt",
        "address": "Marktstraße 1, 70372 Stuttgart, Germany",
        "latitude": 48.8083,
        "longitude": 9.2200,
        "notes": "Bad Cannstatt parking"
    }
]

ORDERS = [
    {
        "order_number": "ORD-2024-001",
        "customer_name": "Thomas Müller",
        "customer_phone": "+49 711 12345678",
        "customer_email": "thomas.mueller@example.de",
        "delivery_address": "Königstraße 28, 70173 Stuttgart, Germany",
        "latitude": 48.7784,
        "longitude": 9.1829,
        "description": "Office supplies delivery",
        "priority": "normal",
        "status": "pending",
        "delivery_time_window_start": datetime.now() + timedelta(days=1),
        "delivery_time_window_end": datetime.now() + timedelta(days=2)
    },
    {
        "order_number": "ORD-2024-002",
        "customer_name": "Sarah Schmidt",
        "customer_phone": "+49 711 23456789",
        "customer_email": "sarah.schmidt@example.de",
        "delivery_address": "Schlossplatz 1, 70173 Stuttgart, Germany",
        "latitude": 48.7784,
        "longitude": 9.1829,
        "description": "Urgent delivery",
        "priority": "high",
        "status": "pending",
        "delivery_time_window_start": datetime.now() + timedelta(hours=2),
        "delivery_time_window_end": datetime.now() + timedelta(hours=6)
    },
    {
        "order_number": "ORD-2024-003",
        "customer_name": "Hans Weber",
        "customer_phone": "+49 711 34567890",
        "customer_email": "hans.weber@example.de",
        "delivery_address": "Marienplatz 1, 70178 Stuttgart, Germany",
        "latitude": 48.7758,
        "longitude": 9.1829,
        "description": "Standard delivery",
        "priority": "normal",
        "status": "pending",
        "delivery_time_window_start": datetime.now() + timedelta(days=1),
        "delivery_time_window_end": datetime.now() + timedelta(days=2)
    },
    {
        "order_number": "ORD-2024-004",
        "customer_name": "Maria Fischer",
        "customer_phone": "+49 711 45678901",
        "customer_email": "maria.fischer@example.de",
        "delivery_address": "Rotebühlplatz 1, 70178 Stuttgart, Germany",
        "latitude": 48.7744,
        "longitude": 9.1708,
        "description": "Home delivery",
        "priority": "normal",
        "status": "pending",
        "delivery_time_window_start": datetime.now() + timedelta(days=1),
        "delivery_time_window_end": datetime.now() + timedelta(days=2)
    },
    {
        "order_number": "ORD-2024-005",
        "customer_name": "Peter Klein",
        "customer_phone": "+49 711 56789012",
        "customer_email": "peter.klein@example.de",
        "delivery_address": "Feuerseeplatz 1, 70178 Stuttgart, Germany",
        "latitude": 48.7700,
        "longitude": 9.1700,
        "description": "Business delivery",
        "priority": "normal",
        "status": "pending",
        "delivery_time_window_start": datetime.now() + timedelta(days=1),
        "delivery_time_window_end": datetime.now() + timedelta(days=2)
    },
    {
        "order_number": "ORD-2024-006",
        "customer_name": "Julia Becker",
        "customer_phone": "+49 711 67890123",
        "customer_email": "julia.becker@example.de",
        "delivery_address": "Marktstraße 15, 70372 Stuttgart, Germany",
        "latitude": 48.8083,
        "longitude": 9.2200,
        "description": "Express delivery",
        "priority": "high",
        "status": "pending",
        "delivery_time_window_start": datetime.now() + timedelta(hours=1),
        "delivery_time_window_end": datetime.now() + timedelta(hours=4)
    },
    {
        "order_number": "ORD-2024-007",
        "customer_name": "Markus Wagner",
        "customer_phone": "+49 711 78901234",
        "customer_email": "markus.wagner@example.de",
        "delivery_address": "Eberhardstraße 10, 70173 Stuttgart, Germany",
        "latitude": 48.7800,
        "longitude": 9.1750,
        "description": "Standard delivery",
        "priority": "normal",
        "status": "pending",
        "delivery_time_window_start": datetime.now() + timedelta(days=1),
        "delivery_time_window_end": datetime.now() + timedelta(days=2)
    },
    {
        "order_number": "ORD-2024-008",
        "customer_name": "Sophie Hoffmann",
        "customer_phone": "+49 711 89012345",
        "customer_email": "sophie.hoffmann@example.de",
        "delivery_address": "Calwer Straße 5, 70173 Stuttgart, Germany",
        "latitude": 48.7770,
        "longitude": 9.1800,
        "description": "Home delivery",
        "priority": "normal",
        "status": "pending",
        "delivery_time_window_start": datetime.now() + timedelta(days=1),
        "delivery_time_window_end": datetime.now() + timedelta(days=2)
    },
    {
        "order_number": "ORD-2024-009",
        "customer_name": "Andreas Bauer",
        "customer_phone": "+49 711 90123456",
        "customer_email": "andreas.bauer@example.de",
        "delivery_address": "Tübinger Straße 20, 70178 Stuttgart, Germany",
        "latitude": 48.7720,
        "longitude": 9.1650,
        "description": "Business delivery",
        "priority": "normal",
        "status": "pending",
        "delivery_time_window_start": datetime.now() + timedelta(days=1),
        "delivery_time_window_end": datetime.now() + timedelta(days=2)
    },
    {
        "order_number": "ORD-2024-010",
        "customer_name": "Nina Schulz",
        "customer_phone": "+49 711 01234567",
        "customer_email": "nina.schulz@example.de",
        "delivery_address": "Wilhelmsplatz 1, 70182 Stuttgart, Germany",
        "latitude": 48.7680,
        "longitude": 9.1600,
        "description": "Urgent delivery",
        "priority": "urgent",
        "status": "pending",
        "delivery_time_window_start": datetime.now() + timedelta(hours=1),
        "delivery_time_window_end": datetime.now() + timedelta(hours=3)
    },
    {
        "order_number": "ORD-2024-011",
        "customer_name": "Stefan Koch",
        "customer_phone": "+49 711 12345098",
        "customer_email": "stefan.koch@example.de",
        "delivery_address": "Hauptstätter Straße 50, 70178 Stuttgart, Germany",
        "latitude": 48.7740,
        "longitude": 9.1720,
        "description": "Standard delivery",
        "priority": "normal",
        "status": "pending",
        "delivery_time_window_start": datetime.now() + timedelta(days=1),
        "delivery_time_window_end": datetime.now() + timedelta(days=2)
    },
    {
        "order_number": "ORD-2024-012",
        "customer_name": "Laura Meier",
        "customer_phone": "+49 711 23450987",
        "customer_email": "laura.meier@example.de",
        "delivery_address": "Neckarstraße 30, 70182 Stuttgart, Germany",
        "latitude": 48.7700,
        "longitude": 9.1750,
        "description": "Home delivery",
        "priority": "normal",
        "status": "pending",
        "delivery_time_window_start": datetime.now() + timedelta(days=1),
        "delivery_time_window_end": datetime.now() + timedelta(days=2)
    }
]


def setup_database():
    """Populate database with sample data"""
    print("Setting up database with sample data...")
    print("=" * 60)

    db = SessionLocal()
    results = {
        "drivers": 0,
        "depots": 0,
        "parking": 0,
        "orders": 0
    }

    try:
        # Add drivers
        print("\n📦 Adding drivers...")
        for driver_data in DRIVERS:
            existing = db.query(Driver).filter(Driver.name == driver_data["name"]).first()
            if existing:
                print(f"  ⚠️  Driver {driver_data['name']} already exists")
                continue

            driver = Driver(**driver_data)
            db.add(driver)
            results["drivers"] += 1
            print(f"  ✅ Added driver: {driver_data['name']}")

        # Add depots
        print("\n🏭 Adding depots...")
        for depot_data in DEPOTS:
            existing = db.query(Depot).filter(Depot.name == depot_data["name"]).first()
            if existing:
                print(f"  ⚠️  Depot {depot_data['name']} already exists")
                continue

            depot = Depot(**depot_data)
            db.add(depot)
            results["depots"] += 1
            print(f"  ✅ Added depot: {depot_data['name']}")

        # Add parking locations
        print("\n🅿️  Adding parking locations...")
        for parking_data in PARKING_LOCATIONS:
            existing = db.query(ParkingLocation).filter(
                ParkingLocation.name == parking_data["name"]
            ).first()
            if existing:
                print(f"  ⚠️  Parking {parking_data['name']} already exists")
                continue

            parking = ParkingLocation(**parking_data)
            db.add(parking)
            results["parking"] += 1
            print(f"  ✅ Added parking: {parking_data['name']}")

        # Add orders
        print("\n📋 Adding orders...")
        for order_data in ORDERS:
            existing = db.query(Order).filter(
                Order.order_number == order_data["order_number"]
            ).first()
            if existing:
                print(f"  ⚠️  Order {order_data['order_number']} already exists")
                continue

            order = Order(**order_data)
            db.add(order)
            results["orders"] += 1
            print(f"  ✅ Added order: {order_data['order_number']} - {order_data['delivery_address']}")

        db.commit()

        print("\n" + "=" * 60)
        print("✅ Database setup complete!")
        print(f"\nSummary:")
        print(f"  - Drivers: {results['drivers']} added")
        print(f"  - Depots: {results['depots']} added")
        print(f"  - Parking locations: {results['parking']} added")
        print(f"  - Orders: {results['orders']} added")
        print("\nYou can now create routes and optimize them!")

    except Exception as e:
        db.rollback()
        print(f"\n❌ Error setting up database: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()

    return True


if __name__ == "__main__":
    success = setup_database()
    sys.exit(0 if success else 1)
