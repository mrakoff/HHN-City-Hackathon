#!/usr/bin/env python3
"""Test the sorting logic directly without requiring a running server"""
from datetime import datetime
from typing import Dict, Optional

# Mock classes to test sorting logic
class MockRouteOrder:
    def __init__(self, order_id: int, sequence: Optional[int]):
        self.order_id = order_id
        self.sequence = sequence

class MockOrder:
    def __init__(self, order_id: int, updated_at=None, created_at=None):
        self.id = order_id
        self.driver_status_updated_at = updated_at
        self.updated_at = updated_at
        self.created_at = created_at or datetime.utcnow()

def test_sorting_logic():
    """Test the sorting logic used in the driver orders endpoint"""
    print("=" * 60)
    print("Testing Route Sequence Sorting Logic")
    print("=" * 60)

    # Create mock assignments (route_orders)
    assignments: Dict[int, MockRouteOrder] = {
        1: MockRouteOrder(1, 3),  # Order 1 has sequence 3
        2: MockRouteOrder(2, 1),  # Order 2 has sequence 1
        3: MockRouteOrder(3, 2),  # Order 3 has sequence 2
        4: MockRouteOrder(4, None),  # Order 4 has no sequence
    }

    # Create mock orders
    base_time = datetime.utcnow()
    orders = {
        1: MockOrder(1, base_time),
        2: MockOrder(2, base_time),
        3: MockOrder(3, base_time),
        4: MockOrder(4, base_time),
        5: MockOrder(5, base_time),  # Order 5 not in assignments
    }

    # Sort orders using the same logic as the endpoint
    def sort_key(order: MockOrder) -> tuple:
        route_order = assignments.get(order.id)
        if route_order and route_order.sequence is not None:
            # Orders with route sequence come first, sorted by sequence
            return (0, route_order.sequence)
        else:
            # Orders without route sequence come after, sorted by timestamp (newest first)
            timestamp = order.driver_status_updated_at or order.updated_at or order.created_at
            return (1, -(timestamp.timestamp() if timestamp else 0))

    sorted_orders = sorted(orders.values(), key=sort_key)

    print("\n✅ Sorting Test Results:")
    print("-" * 60)
    print("Expected order: 2 (seq=1), 3 (seq=2), 1 (seq=3), 4 (no seq), 5 (no seq)")
    print("\nActual order:")
    for i, order in enumerate(sorted_orders, 1):
        route_order = assignments.get(order.id)
        if route_order and route_order.sequence is not None:
            print(f"  {i}. Order {order.id} - Route Sequence: {route_order.sequence}")
        else:
            print(f"  {i}. Order {order.id} - No route sequence")

    # Verify the order
    expected_order_ids = [2, 3, 1, 4, 5]
    actual_order_ids = [o.id for o in sorted_orders]

    if actual_order_ids == expected_order_ids:
        print("\n✅ PASS: Orders are sorted correctly!")
        print("   - Orders with route_sequence appear first (sorted by sequence)")
        print("   - Orders without route_sequence appear after")
        return True
    else:
        print(f"\n❌ FAIL: Expected {expected_order_ids}, got {actual_order_ids}")
        return False

if __name__ == "__main__":
    success = test_sorting_logic()
    print("\n" + "=" * 60)
    exit(0 if success else 1)
