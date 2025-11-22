from typing import List, Optional
from datetime import datetime, timedelta
from ..models import OrderCreate


def calculate_priority_from_time_window(
    delivery_time_window_start: Optional[datetime] = None,
    delivery_time_window_end: Optional[datetime] = None,
    explicit_priority: Optional[str] = None
) -> str:
    """
    Calculate priority based on delivery time window.
    If explicit priority is provided, use it. Otherwise:
    - No time window = low priority
    - Time window > 3 days away = normal priority
    - Time window 1-3 days away = high priority
    - Time window < 24 hours away = urgent priority
    """
    if explicit_priority:
        return explicit_priority

    if not delivery_time_window_start or not delivery_time_window_end:
        return "low"

    now = datetime.now()
    time_until_start = delivery_time_window_start - now

    # If the time window has already passed, mark as urgent
    if time_until_start.total_seconds() < 0:
        return "urgent"

    hours_until_start = time_until_start.total_seconds() / 3600

    if hours_until_start < 24:
        return "urgent"
    elif hours_until_start < 72:  # 3 days
        return "high"
    elif hours_until_start < 168:  # 7 days
        return "normal"
    else:
        return "low"


def validate_order(order: OrderCreate) -> List[str]:
    """
    Validate an order and return list of validation errors
    Returns empty list if order is valid
    """
    errors = []

    # Check required fields
    if not order.delivery_address or not order.delivery_address.strip():
        errors.append("Delivery address is required")

    # Validate address format (basic check)
    if order.delivery_address and len(order.delivery_address.strip()) < 5:
        errors.append("Delivery address seems too short")

    # Validate email if provided
    if order.customer_email:
        if "@" not in order.customer_email or "." not in order.customer_email:
            errors.append("Invalid email format")

    # Validate phone if provided
    if order.customer_phone:
        # Remove common phone formatting characters
        phone_digits = "".join(c for c in order.customer_phone if c.isdigit())
        if len(phone_digits) < 7:
            errors.append("Phone number seems too short")

    # Validate time window
    if order.delivery_time_window_start and order.delivery_time_window_end:
        if order.delivery_time_window_start >= order.delivery_time_window_end:
            errors.append("Delivery time window start must be before end")

    # Validate priority
    valid_priorities = ["low", "normal", "high", "urgent"]
    if order.priority and order.priority not in valid_priorities:
        errors.append(f"Priority must be one of: {', '.join(valid_priorities)}")

    # Check if items are provided but empty
    if order.items is not None and len(order.items) == 0:
        errors.append("Order has no items")

    return errors
