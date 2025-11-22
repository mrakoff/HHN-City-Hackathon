#!/usr/bin/env python3
"""
Test script specifically for unfinished orders - orders with missing information
that should appear in the unfinished orders view
"""

import sys

try:
    import requests
except ImportError:
    print("Error: 'requests' module not found.")
    print("Install it with: pip install requests")
    sys.exit(1)

API_BASE = "http://localhost:8000/api"

def test_unfinished_order_missing_address():
    """Test order with missing delivery address - should be unfinished"""
    print("\n" + "="*60)
    print("Test 1: Order with MISSING DELIVERY ADDRESS")
    print("="*60)

    text = """
    Customer Name: John Doe
    Phone: +49 30 12345678
    Email: john.doe@example.com
    Description: Need delivery ASAP
    Items: 5x Widget A
    """

    try:
        response = requests.post(
            f"{API_BASE}/orders/parse-text",
            json={
                "text": text,
                "source": "phone"
            }
        )
        response.raise_for_status()
        order = response.json()

        print(f"✅ Order created: ID {order.get('id')}, Number: {order.get('order_number')}")
        print(f"   Delivery Address: '{order.get('delivery_address')}'")
        print(f"   Validation Errors: {order.get('validation_errors')}")

        # Check if it's marked as unfinished
        has_errors = order.get('validation_errors') and len(order.get('validation_errors', [])) > 0
        missing_address = not order.get('delivery_address') or order.get('delivery_address', '').strip() == ''
        is_unfinished = has_errors or missing_address

        if is_unfinished:
            print(f"   ✅ CORRECTLY marked as UNFINISHED")
        else:
            print(f"   ❌ ERROR: Should be marked as unfinished but isn't")

        # Verify it appears in unfinished orders list
        response = requests.get(f"{API_BASE}/orders?unfinished=true")
        response.raise_for_status()
        unfinished_orders = response.json()
        order_ids = [o['id'] for o in unfinished_orders]

        if order.get('id') in order_ids:
            print(f"   ✅ Appears in unfinished orders list")
        else:
            print(f"   ❌ ERROR: Does not appear in unfinished orders list")

        return order

    except Exception as e:
        print(f"❌ FAILED: {str(e)}")
        return None

def test_unfinished_order_invalid_email():
    """Test order with invalid email - should have validation errors"""
    print("\n" + "="*60)
    print("Test 2: Order with INVALID EMAIL")
    print("="*60)

    order_data = {
        "delivery_address": "Test Street 123, Berlin",
        "customer_name": "Test Customer",
        "customer_email": "not-a-valid-email",  # Invalid email
        "source": "manual"
    }

    try:
        response = requests.post(
            f"{API_BASE}/orders",
            json=order_data
        )
        response.raise_for_status()
        order = response.json()

        print(f"✅ Order created: ID {order.get('id')}, Number: {order.get('order_number')}")
        print(f"   Email: '{order.get('customer_email')}'")
        print(f"   Validation Errors: {order.get('validation_errors')}")

        has_errors = order.get('validation_errors') and len(order.get('validation_errors', [])) > 0

        if has_errors:
            print(f"   ✅ CORRECTLY has validation errors")
            # Check if it appears in unfinished orders
            response = requests.get(f"{API_BASE}/orders?unfinished=true")
            response.raise_for_status()
            unfinished_orders = response.json()
            order_ids = [o['id'] for o in unfinished_orders]

            if order.get('id') in order_ids:
                print(f"   ✅ Appears in unfinished orders list")
            else:
                print(f"   ❌ ERROR: Should appear in unfinished orders but doesn't")
        else:
            print(f"   ❌ ERROR: Should have validation errors but doesn't")

        return order

    except Exception as e:
        print(f"❌ FAILED: {str(e)}")
        return None

def test_unfinished_order_short_address():
    """Test order with too short address - should have validation errors"""
    print("\n" + "="*60)
    print("Test 3: Order with TOO SHORT ADDRESS")
    print("="*60)

    order_data = {
        "delivery_address": "123",  # Too short
        "customer_name": "Test Customer",
        "source": "manual"
    }

    try:
        response = requests.post(
            f"{API_BASE}/orders",
            json=order_data
        )
        response.raise_for_status()
        order = response.json()

        print(f"✅ Order created: ID {order.get('id')}, Number: {order.get('order_number')}")
        print(f"   Address: '{order.get('delivery_address')}'")
        print(f"   Validation Errors: {order.get('validation_errors')}")

        has_errors = order.get('validation_errors') and len(order.get('validation_errors', [])) > 0

        if has_errors:
            print(f"   ✅ CORRECTLY has validation errors (address too short)")
        else:
            print(f"   ⚠️  No validation errors (may be acceptable if address is not empty)")

        return order

    except Exception as e:
        print(f"❌ FAILED: {str(e)}")
        return None

def test_complete_order():
    """Test complete order - should NOT be unfinished"""
    print("\n" + "="*60)
    print("Test 4: COMPLETE ORDER (should NOT be unfinished)")
    print("="*60)

    order_data = {
        "delivery_address": "Hauptstraße 123, 10115 Berlin, Germany",
        "customer_name": "Complete Customer",
        "customer_phone": "+49 30 12345678",
        "customer_email": "complete@example.com",
        "description": "Complete test order",
        "items": [{"name": "Item 1", "quantity": 5}],
        "source": "manual"
    }

    try:
        response = requests.post(
            f"{API_BASE}/orders",
            json=order_data
        )
        response.raise_for_status()
        order = response.json()

        print(f"✅ Order created: ID {order.get('id')}, Number: {order.get('order_number')}")
        print(f"   Validation Errors: {order.get('validation_errors')}")

        has_errors = order.get('validation_errors') and len(order.get('validation_errors', [])) > 0
        missing_address = not order.get('delivery_address') or order.get('delivery_address', '').strip() == ''
        is_unfinished = has_errors or missing_address

        if not is_unfinished:
            print(f"   ✅ CORRECTLY NOT marked as unfinished")
        else:
            print(f"   ❌ ERROR: Should NOT be unfinished but is")

        # Verify it does NOT appear in unfinished orders
        response = requests.get(f"{API_BASE}/orders?unfinished=true")
        response.raise_for_status()
        unfinished_orders = response.json()
        order_ids = [o['id'] for o in unfinished_orders]

        if order.get('id') not in order_ids:
            print(f"   ✅ Does NOT appear in unfinished orders list (correct)")
        else:
            print(f"   ❌ ERROR: Should NOT appear in unfinished orders but does")

        return order

    except Exception as e:
        print(f"❌ FAILED: {str(e)}")
        return None

def test_unfinished_orders_filter():
    """Test the unfinished orders filter endpoint"""
    print("\n" + "="*60)
    print("Test 5: UNFINISHED ORDERS FILTER")
    print("="*60)

    try:
        # Get all orders
        response = requests.get(f"{API_BASE}/orders")
        response.raise_for_status()
        all_orders = response.json()

        # Get unfinished orders
        response = requests.get(f"{API_BASE}/orders?unfinished=true")
        response.raise_for_status()
        unfinished_orders = response.json()

        print(f"Total orders: {len(all_orders)}")
        print(f"Unfinished orders: {len(unfinished_orders)}")

        # Verify unfinished orders have issues
        print("\nUnfinished orders details:")
        for order in unfinished_orders:
            has_errors = order.get('validation_errors') and len(order.get('validation_errors', [])) > 0
            missing_address = not order.get('delivery_address') or order.get('delivery_address', '').strip() == ''

            print(f"  Order #{order.get('id')} ({order.get('order_number')}):")
            print(f"    Address: '{order.get('delivery_address')}'")
            print(f"    Has errors: {has_errors}")
            print(f"    Missing address: {missing_address}")
            print(f"    Validation errors: {order.get('validation_errors')}")

            if not (has_errors or missing_address):
                print(f"    ⚠️  WARNING: This order shouldn't be in unfinished list!")

        print(f"\n✅ Filter test completed")
        return True

    except Exception as e:
        print(f"❌ FAILED: {str(e)}")
        return False

def main():
    print("\n" + "="*60)
    print("UNFINISHED ORDERS TEST SUITE")
    print("="*60)
    print("\nThis test verifies that orders with missing information")
    print("are correctly marked as unfinished and appear in the")
    print("unfinished orders view.")

    try:
        # Check if server is running
        response = requests.get(f"{API_BASE.replace('/api', '')}/api/health", timeout=2)
        if response.status_code != 200:
            print("❌ Server is not responding correctly")
            return False
    except requests.exceptions.RequestException:
        print("❌ Cannot connect to server. Make sure the backend is running on http://localhost:8000")
        return False

    # Run tests
    test_unfinished_order_missing_address()
    test_unfinished_order_invalid_email()
    test_unfinished_order_short_address()
    test_complete_order()
    test_unfinished_orders_filter()

    print("\n" + "="*60)
    print("TEST SUITE COMPLETED")
    print("="*60)
    print("\nCheck the results above to verify:")
    print("1. Orders with missing addresses are marked as unfinished")
    print("2. Orders with validation errors are marked as unfinished")
    print("3. Complete orders are NOT marked as unfinished")
    print("4. Unfinished orders appear in the unfinished orders filter")

    return True

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
