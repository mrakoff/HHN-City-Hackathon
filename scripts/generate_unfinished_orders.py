#!/usr/bin/env python3
"""
Generate mock unfinished orders - orders with missing or insufficient information.
These orders will appear in the "Unfinished Orders" view.
"""

import sys
import os
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any

# Add parent directory to path to import backend modules
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from backend.database import SessionLocal, Order
    from backend.models import OrderCreate
    from backend.services.order_validator import validate_order
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
except ImportError as e:
    print(f"Error importing backend modules: {e}")
    print("Make sure you're running this from the project root directory")
    sys.exit(1)


# Mock unfinished orders - various scenarios of missing/invalid information
UNFINISHED_ORDERS = [
    {
        "order_number": None,  # Will be auto-generated
        "customer_name": "Anna Weber",
        "customer_email": None,
        "customer_phone": "+49 7131",
        "delivery_address": "",  # MISSING ADDRESS
        "description": "Urgent delivery needed but address was unclear in phone call",
        "items": [{"name": "Product A", "quantity": 3}],
        "priority": "urgent",
        "delivery_time_window_start": datetime.now() + timedelta(hours=6),
        "delivery_time_window_end": datetime.now() + timedelta(hours=12),
        "source": "phone",
        "validation_errors": ["Delivery address is required"]
    },
    {
        "order_number": None,
        "customer_name": "Max Mustermann",
        "customer_email": "invalid-email-format",  # INVALID EMAIL
        "customer_phone": "+49 7131 123456",
        "delivery_address": "Hauptstraße 45, 74072 Heilbronn",
        "description": "Customer provided invalid email address",
        "items": [{"name": "Widget X", "quantity": 2}],
        "priority": "normal",
        "source": "email",
        "validation_errors": ["Invalid email format"]
    },
    {
        "order_number": None,
        "customer_name": "Sarah Klein",
        "customer_email": "sarah.klein@example.de",
        "customer_phone": "123",  # TOO SHORT PHONE
        "delivery_address": "Allee 78, 74076 Heilbronn",
        "description": "Phone number incomplete",
        "items": [{"name": "Item 1", "quantity": 5}],
        "priority": "normal",
        "source": "phone",
        "validation_errors": ["Phone number seems too short"]
    },
    {
        "order_number": None,
        "customer_name": "Peter Schmidt",
        "customer_email": "peter.schmidt@example.de",
        "customer_phone": None,
        "delivery_address": "123",  # ADDRESS TOO SHORT
        "description": "Address incomplete - only house number provided",
        "items": [{"name": "Component B", "quantity": 1}],
        "priority": "high",
        "source": "fax",
        "validation_errors": ["Delivery address seems too short"]
    },
    {
        "order_number": None,
        "customer_name": "Julia Fischer",
        "customer_email": None,
        "customer_phone": None,
        "delivery_address": "",  # MISSING ADDRESS
        "description": "Order received via mail but address is illegible",
        "items": None,  # NO ITEMS
        "priority": "normal",
        "source": "mail",
        "validation_errors": ["Delivery address is required", "Order has no items"]
    },
    {
        "order_number": None,
        "customer_name": "Michael Bauer",
        "customer_email": "m.bauer@test",
        "customer_phone": "+49 7131 987654",
        "delivery_address": "Kiliansplatz, Heilbronn",  # VAGUE ADDRESS
        "description": "Address needs clarification",
        "items": [{"name": "Package A", "quantity": 2}],
        "priority": "normal",
        "delivery_time_window_start": datetime.now() + timedelta(days=2),
        "delivery_time_window_end": datetime.now() + timedelta(days=1),  # INVALID WINDOW
        "source": "email",
        "validation_errors": ["Delivery time window start must be before end", "Invalid email format"]
    },
    {
        "order_number": None,
        "customer_name": "Lisa Wagner",
        "customer_email": "lisa.wagner@example.de",
        "customer_phone": None,
        "delivery_address": None,  # MISSING ADDRESS
        "description": "Order form partially damaged",
        "items": [{"name": "Product Y", "quantity": 4}],
        "priority": "urgent",
        "source": "mail",
        "validation_errors": ["Delivery address is required"]
    },
    {
        "order_number": None,
        "customer_name": "Thomas Neumann",
        "customer_email": "thomas.neumann@example.de",
        "customer_phone": "+49 7131 555666",
        "delivery_address": "Willy-Brandt-Platz",  # INCOMPLETE ADDRESS
        "description": None,
        "items": [],  # EMPTY ITEMS LIST
        "priority": "normal",
        "source": "phone",
        "validation_errors": ["Delivery address seems too short", "Order has no items"]
    },
    {
        "order_number": None,
        "customer_name": None,  # MISSING NAME
        "customer_email": "unknown@example.de",
        "customer_phone": "+49 7131 111222",
        "delivery_address": "Crailsheimstraße, Heilbronn",  # VAGUE
        "description": "Anonymous order - customer name missing",
        "items": [{"name": "Item Z", "quantity": 1}],
        "priority": "invalid_priority",  # INVALID PRIORITY
        "source": "email",
        "validation_errors": ["Delivery address seems too short", "Priority must be one of: low, normal, high, urgent"]
    },
    {
        "order_number": None,
        "customer_name": "Daniel Richter",
        "customer_email": "daniel@",  # INVALID EMAIL
        "customer_phone": "555",  # TOO SHORT
        "delivery_address": "",  # MISSING
        "description": "Multiple fields missing",
        "items": None,
        "priority": "normal",
        "source": "phone",
        "validation_errors": ["Delivery address is required", "Invalid email format", "Phone number seems too short", "Order has no items"]
    }
]


def create_unfinished_order(db, order_data: Dict[str, Any]) -> Order:
    """Create an unfinished order in the database"""
    # Generate order number if not provided
    if not order_data.get('order_number'):
        now = datetime.now()
        date_str = now.strftime("%d%m%y")
        # Count existing orders to get sequence
        existing_count = db.query(Order).filter(
            Order.order_number.like(f"ORD-{date_str}-%")
        ).count()
        seq = existing_count + 1
        order_data['order_number'] = f"ORD-{date_str}-{seq:04d}"

    # Create order object
    db_order = Order(
        order_number=order_data.get('order_number'),
        customer_name=order_data.get('customer_name'),
        customer_email=order_data.get('customer_email'),
        customer_phone=order_data.get('customer_phone'),
        delivery_address=order_data.get('delivery_address') or "",
        description=order_data.get('description'),
        items=order_data.get('items'),
        priority=order_data.get('priority', 'normal'),
        status="pending",
        source=order_data.get('source', 'manual'),
        delivery_time_window_start=order_data.get('delivery_time_window_start'),
        delivery_time_window_end=order_data.get('delivery_time_window_end'),
        validation_errors=order_data.get('validation_errors', []),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )

    # If validation_errors weren't provided, validate the order
    if not order_data.get('validation_errors'):
        # Create OrderCreate object for validation
        order_create = OrderCreate(**{
            k: v for k, v in order_data.items()
            if k not in ['order_number', 'source', 'validation_errors']
        })
        validation_errors = validate_order(order_create)
        if validation_errors:
            db_order.validation_errors = validation_errors

    db.add(db_order)
    db.commit()
    db.refresh(db_order)

    return db_order


def main():
    """Generate unfinished orders"""
    print("="*60)
    print("Generating Mock Unfinished Orders")
    print("="*60)
    print()

    # Create database session
    db = SessionLocal()

    try:
        created_orders = []

        for idx, order_data in enumerate(UNFINISHED_ORDERS, 1):
            try:
                print(f"[{idx}/{len(UNFINISHED_ORDERS)}] Creating unfinished order...")

                order = create_unfinished_order(db, order_data)

                # Get validation errors for display
                errors = order.validation_errors or []
                missing_address = not order.delivery_address or order.delivery_address.strip() == ""

                print(f"  ✅ Created: {order.order_number}")
                print(f"     Customer: {order.customer_name or 'MISSING'}")
                print(f"     Address: '{order.delivery_address or 'MISSING'}'")
                if errors:
                    print(f"     Errors: {', '.join(errors[:3])}{'...' if len(errors) > 3 else ''}")
                elif missing_address:
                    print(f"     Status: Missing address (unfinished)")
                print()

                created_orders.append(order)

            except Exception as e:
                print(f"  ❌ Failed to create order {idx}: {e}")
                print()
                continue

        print("="*60)
        print(f"✅ Successfully created {len(created_orders)} unfinished orders")
        print("="*60)
        print()
        print("These orders will appear in the 'Unfinished Orders' view because they:")
        print("  - Have missing delivery addresses, OR")
        print("  - Have validation errors")
        print()
        print("To verify, check the orders page and click 'Unfinished Orders'")

        return created_orders

    except Exception as e:
        print(f"❌ Error: {e}")
        db.rollback()
        return []
    finally:
        db.close()


if __name__ == "__main__":
    main()
