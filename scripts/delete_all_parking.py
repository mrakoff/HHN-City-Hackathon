#!/usr/bin/env python3
"""Delete all parking locations from database, keeping only depots"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from backend.database import SessionLocal, ParkingLocation

def delete_all_parking():
    db = SessionLocal()
    try:
        count = db.query(ParkingLocation).count()
        print(f"Found {count} parking location(s)")

        if count > 0:
            db.query(ParkingLocation).delete()
            db.commit()
            print(f"✅ Deleted {count} parking location(s)")
        else:
            print("No parking locations to delete")

    except Exception as e:
        db.rollback()
        print(f"❌ Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    delete_all_parking()
