#!/usr/bin/env python3
"""Test script to verify driver orders are sorted by route_sequence"""
import sys
import requests
import json
from typing import List, Dict

API_BASE = "http://localhost:8000/api"

def test_driver_orders_sorting():
    """Test that driver orders are sorted by route_sequence"""
    print("=" * 60)
    print("Testing Driver Orders Endpoint - Route Sequence Sorting")
    print("=" * 60)

    # Check if server is running
    try:
        response = requests.get(f"{API_BASE.replace('/api', '')}/api/health", timeout=2)
        if response.status_code != 200:
            print("❌ Server is not responding correctly")
            return False
    except requests.exceptions.RequestException as e:
        print(f"❌ Cannot connect to server at {API_BASE}")
        print(f"   Error: {e}")
        print("\n💡 Make sure the backend server is running:")
        print("   python3 -m uvicorn backend.main:app --reload --port 8000")
        return False

    print("✅ Server is running\n")

    # Get all drivers
    try:
        response = requests.get(f"{API_BASE}/drivers")
        if response.status_code != 200:
            print(f"❌ Failed to get drivers: {response.status_code}")
            return False
        drivers = response.json()
        if not drivers:
            print("⚠️  No drivers found in database")
            print("   Create drivers first using the planner interface")
            return True
        print(f"✅ Found {len(drivers)} driver(s)\n")
    except Exception as e:
        print(f"❌ Error getting drivers: {e}")
        return False

    # Test each driver
    all_passed = True
    for driver in drivers:
        driver_id = driver["id"]
        driver_name = driver.get("name", f"Driver {driver_id}")
        print(f"Testing driver: {driver_name} (ID: {driver_id})")
        print("-" * 60)

        try:
            # Get driver orders
            response = requests.get(
                f"{API_BASE}/orders/driver/orders",
                params={"driver_id": driver_id, "include_completed": False}
            )

            if response.status_code != 200:
                print(f"  ❌ Failed to get orders: {response.status_code}")
                print(f"     {response.text}")
                all_passed = False
                continue

            orders = response.json()
            if not orders:
                print(f"  ⚠️  No orders assigned to this driver")
                print()
                continue

            print(f"  ✅ Found {len(orders)} order(s)")

            # Check sorting
            has_route_sequence = False
            sequence_values = []
            orders_without_sequence = []

            for i, order_assignment in enumerate(orders):
                route_sequence = order_assignment.get("route_sequence")
                order_id = order_assignment.get("order", {}).get("id")
                order_number = order_assignment.get("order", {}).get("order_number", f"#{order_id}")

                if route_sequence is not None:
                    has_route_sequence = True
                    sequence_values.append((i, route_sequence, order_number))
                else:
                    orders_without_sequence.append((i, order_number))

            if has_route_sequence:
                # Verify sequences are in ascending order
                sequences = [seq for _, seq, _ in sequence_values]
                is_sorted = sequences == sorted(sequences)

                if is_sorted:
                    print(f"  ✅ Orders with route_sequence are sorted correctly")
                    print(f"     Sequence order: {sequences}")
                else:
                    print(f"  ❌ Orders with route_sequence are NOT sorted correctly!")
                    print(f"     Current order: {sequences}")
                    print(f"     Expected: {sorted(sequences)}")
                    all_passed = False

                # Show order details
                print(f"\n  Order sequence details:")
                for idx, seq, order_num in sequence_values:
                    print(f"    Position {idx}: Stop #{seq} - Order {order_num}")

            if orders_without_sequence:
                print(f"\n  ⚠️  {len(orders_without_sequence)} order(s) without route_sequence")
                print(f"     (These appear after sequenced orders)")

            print()

        except Exception as e:
            print(f"  ❌ Error testing driver {driver_id}: {e}")
            import traceback
            traceback.print_exc()
            all_passed = False

    print("=" * 60)
    if all_passed:
        print("✅ All tests passed!")
    else:
        print("❌ Some tests failed")
    print("=" * 60)

    return all_passed

if __name__ == "__main__":
    success = test_driver_orders_sorting()
    sys.exit(0 if success else 1)
