from typing import List, Dict, Tuple, Optional, Any
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)

# Color palette for routes (distinct colors)
ROUTE_COLORS = [
    "#9b59b6",  # Purple
    "#e91e63",  # Pink
    "#00bcd4",  # Cyan
    "#4caf50",  # Green
    "#ff9800",  # Orange
    "#2196f3",  # Blue
    "#f44336",  # Red
    "#009688",  # Teal
    "#ffc107",  # Amber
    "#795548",  # Brown
    "#607d8b",  # Blue Grey
    "#9c27b0",  # Deep Purple
    "#ff5722",  # Deep Orange
    "#00acc1",  # Cyan
    "#8bc34a",  # Light Green
]


def generate_route_name(driver_name: str, route_index: int) -> str:
    """
    Generate a short route name from driver name
    Examples: "Michael Schneider" -> "MS", "John Doe" -> "JD"
    """
    if not driver_name:
        return f"R{route_index + 1}"

    words = driver_name.split()
    if len(words) >= 2:
        return f"{words[0][0]}{words[1][0]}".upper()
    elif len(words) == 1:
        return f"{words[0][0:2]}".upper()
    else:
        return f"R{route_index + 1}"


def assign_drivers_to_clusters(
    clusters: List[List[int]],
    drivers: List[Dict[str, Any]],
    orders: List[Dict[str, Any]],
    assignment_strategy: str = "balanced"
) -> List[Dict[str, Any]]:
    """
    Assign clusters to drivers

    Args:
        clusters: List of order clusters (each cluster is a list of order indices)
        drivers: List of available drivers
        orders: List of all orders (for calculating workload)
        assignment_strategy: "balanced" (even workload) or "sequential" (round-robin)

    Returns:
        List of route assignments:
        [
            {
                "driver_id": 1,
                "driver_name": "Michael Schneider",
                "order_ids": [1, 2, 3, ...],
                "order_count": 5,
                "route_name": "MS",
                "color": "#9b59b6",
                "route_index": 0
            },
            ...
        ]
    """
    if not clusters or not drivers:
        return []

    # Filter out drivers that shouldn't be used (optional future feature)
    available_drivers = [d for d in drivers if d.get('available', True)]

    if not available_drivers:
        logger.warning("No available drivers, using all drivers")
        available_drivers = drivers

    # Calculate cluster sizes
    cluster_sizes = [len(cluster) for cluster in clusters]

    if assignment_strategy == "balanced":
        # Sort clusters by size (largest first) and drivers by workload
        cluster_with_size = list(enumerate(cluster_sizes))
        cluster_with_size.sort(key=lambda x: x[1], reverse=True)

        # Track driver workloads
        driver_workloads = {d['id']: 0 for d in available_drivers}
        assignments = []

        for cluster_idx, cluster_size in cluster_with_size:
            # Find driver with least workload
            min_workload = min(driver_workloads.values())
            available_driver_ids = [
                driver_id for driver_id, workload
                in driver_workloads.items()
                if workload == min_workload
            ]

            # Use first available driver (or could randomize)
            assigned_driver_id = available_driver_ids[0]
            driver_workloads[assigned_driver_id] += cluster_size

            # Find driver details
            driver = next((d for d in available_drivers if d['id'] == assigned_driver_id), None)
            if not driver:
                continue

            route_index = len(assignments)
            route_name = generate_route_name(driver.get('name', ''), route_index)
            color = ROUTE_COLORS[route_index % len(ROUTE_COLORS)]

            assignments.append({
                "driver_id": assigned_driver_id,
                "driver_name": driver.get('name', f"Driver {assigned_driver_id}"),
                "order_ids": clusters[cluster_idx],
                "order_count": cluster_size,
                "route_name": route_name,
                "color": color,
                "route_index": route_index
            })

        # Sort assignments by driver_id for consistency
        assignments.sort(key=lambda x: x['driver_id'])

    else:  # sequential / round-robin
        assignments = []
        driver_idx = 0

        for cluster_idx, cluster in enumerate(clusters):
            driver = available_drivers[driver_idx % len(available_drivers)]
            driver_idx += 1

            route_index = len(assignments)
            route_name = generate_route_name(driver.get('name', ''), route_index)
            color = ROUTE_COLORS[route_index % len(ROUTE_COLORS)]

            assignments.append({
                "driver_id": driver['id'],
                "driver_name": driver.get('name', f"Driver {driver['id']}"),
                "order_ids": cluster,
                "order_count": len(cluster),
                "route_name": route_name,
                "color": color,
                "route_index": route_index
            })

    logger.info(f"Assigned {len(clusters)} clusters to {len(set(a['driver_id'] for a in assignments))} drivers")
    return assignments


def calculate_route_statistics(
    assignments: List[Dict[str, Any]],
    orders: List[Dict[str, Any]],
    depot: Dict[str, Any],
    total_orders: int
) -> Dict[str, Any]:
    """
    Calculate statistics for the planned routes

    Returns:
        {
            "total_routes": 5,
            "total_orders": 120,
            "total_distance_km": 450.5,
            "total_time_hours": 12.5,
            "drivers_used": 5,
            "unscheduled_orders": 20,
            "average_orders_per_route": 24.0,
            "average_distance_per_route": 90.1
        }
    """
    scheduled_order_ids = set()
    for assignment in assignments:
        scheduled_order_ids.update(assignment['order_ids'])

    unscheduled_orders = total_orders - len(scheduled_order_ids)

    # Calculate estimated distances and times (rough estimates)
    # In production, this would use actual route optimization
    total_distance = sum(
        assignment['order_count'] * 5.0  # Rough estimate: 5km per order
        for assignment in assignments
    )

    total_time_minutes = sum(
        assignment['order_count'] * 15.0  # Rough estimate: 15 min per order
        for assignment in assignments
    )

    drivers_used = len(set(a['driver_id'] for a in assignments))

    return {
        "total_routes": len(assignments),
        "total_orders": len(scheduled_order_ids),
        "total_distance_km": round(total_distance, 2),
        "total_time_minutes": round(total_time_minutes, 1),
        "total_time_hours": round(total_time_minutes / 60.0, 2),
        "drivers_used": drivers_used,
        "unscheduled_orders": unscheduled_orders,
        "average_orders_per_route": round(len(scheduled_order_ids) / len(assignments), 1) if assignments else 0,
        "average_distance_per_route": round(total_distance / len(assignments), 1) if assignments else 0
    }
