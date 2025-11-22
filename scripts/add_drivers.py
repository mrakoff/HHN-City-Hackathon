#!/usr/bin/env python3
"""
Add 5 drivers to the database directly
Run this from the project root directory with: python3 scripts/add_drivers.py
"""

import sys
import os

# Add parent directory to path to import backend modules
project_root = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, os.path.abspath(project_root))

try:
    from backend.database import SessionLocal, Driver
except ImportError as e:
    print(f"Error importing backend modules: {e}")
    print("Make sure you're running this from the project root and dependencies are installed.")
    print("Try: pip install -r requirements.txt")
    sys.exit(1)

DRIVERS = [
    {
        "name": "Michael Schneider",
        "phone": "+49 30 11111111",
        "email": "michael.schneider@delivery.com",
        "status": "available"
    },
    {
        "name": "Anna Weber",
        "phone": "+49 89 22222222",
        "email": "anna.weber@delivery.com",
        "status": "available"
    },
    {
        "name": "Thomas Fischer",
        "phone": "+49 40 33333333",
        "email": "thomas.fischer@delivery.com",
        "status": "on_route"
    },
    {
        "name": "Sarah Müller",
        "phone": "+49 69 44444444",
        "email": "sarah.mueller@delivery.com",
        "status": "available"
    },
    {
        "name": "David Klein",
        "phone": "+49 221 55555555",
        "email": "david.klein@delivery.com",
        "status": "offline"
    }
]

def add_drivers():
    print("Adding 5 drivers to the database...")
    print("="*60)

    db = SessionLocal()
    added_info = []  # Store driver info as dicts to avoid detached instance issues
    failed = []

    try:
        for driver_data in DRIVERS:
            try:
                # Check if driver already exists
                existing = db.query(Driver).filter(Driver.name == driver_data["name"]).first()
                if existing:
                    print(f"⚠️  Driver {driver_data['name']} already exists (ID: {existing.id})")
                    # Store info before session closes
                    added_info.append({
                        "id": existing.id,
                        "name": existing.name,
                        "status": existing.status
                    })
                    continue

                # Create new driver
                driver = Driver(**driver_data)
                db.add(driver)
                db.commit()
                db.refresh(driver)
                # Store info before session closes
                added_info.append({
                    "id": driver.id,
                    "name": driver.name,
                    "status": driver.status
                })
                print(f"✅ Added: {driver.name} (ID: {driver.id})")
            except Exception as e:
                db.rollback()
                failed.append((driver_data['name'], str(e)))
                print(f"❌ Failed to add {driver_data['name']}: {str(e)}")
    finally:
        db.close()

    print("\n" + "="*60)
    print(f"Summary: {len(added_info)} drivers added/existing, {len(failed)} failed")

    if added_info:
        print("\nDrivers in database:")
        for driver_info in added_info:
            print(f"  - {driver_info['name']} ({driver_info['status']})")

    return len(added_info) == len(DRIVERS)

if __name__ == "__main__":
    success = add_drivers()
    exit(0 if success else 1)
