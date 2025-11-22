from typing import List, Dict, Optional, Any
from .route_optimizer import optimize_route, calculate_route_improvement
from .route_calculator import calculate_distance

# Try to use Gemini if available
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False


def suggest_route_optimization(
    depot: Dict[str, float],
    current_route: List[Dict[str, Any]],
    all_orders: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    AI agent that suggests route optimizations
    """
    if not current_route:
        return {"suggestion": "No route to optimize", "improvement": None}

    # Extract order locations from current route
    current_order_locations = [
        {"lat": order["latitude"], "lon": order["longitude"]}
        for order in current_route
        if order.get("latitude") and order.get("longitude")
    ]

    if not current_order_locations:
        return {"suggestion": "Route orders missing location data", "improvement": None}

    # Get current route order indices
    current_indices = list(range(len(current_order_locations)))

    # Optimize route
    optimized_indices = optimize_route(depot, current_order_locations)

    # Calculate improvement
    improvement = calculate_route_improvement(
        current_indices,
        optimized_indices,
        depot,
        current_order_locations
    )

    # Reorder route based on optimization
    optimized_route = [current_route[idx] for idx in optimized_indices]

    suggestion = "Route optimization complete"
    if improvement["improvement_percent"] > 5:
        suggestion = f"Optimization can save {improvement['distance_saved_km']:.2f} km ({improvement['improvement_percent']:.1f}%)"
    elif improvement["improvement_percent"] < 1:
        suggestion = "Current route is already well optimized"

    return {
        "suggestion": suggestion,
        "improvement": improvement,
        "optimized_route": optimized_route,
        "optimized_order_ids": [order["id"] for order in optimized_route]
    }


def suggest_parking_location(
    delivery_address: Dict[str, float],
    parking_locations: List[Dict[str, Any]],
    max_distance_km: float = 0.5
) -> Optional[Dict[str, Any]]:
    """
    AI agent that suggests parking location near delivery address
    """
    if not parking_locations:
        return None

    best_parking = None
    best_distance = float('inf')

    for parking in parking_locations:
        if not parking.get("latitude") or not parking.get("longitude"):
            continue

        distance = calculate_distance(
            delivery_address["lat"], delivery_address["lon"],
            parking["latitude"], parking["longitude"]
        )

        if distance < best_distance and distance <= max_distance_km:
            best_distance = distance
            best_parking = parking

    if best_parking:
        return {
            **best_parking,
            "distance_km": best_distance,
            "suggestion": f"Park at {best_parking.get('name', 'this location')} ({best_distance:.2f} km away)"
        }

    return None


def detect_route_conflicts(
    routes: List[Dict[str, Any]],
    conflict_threshold_km: float = 1.0
) -> List[Dict[str, Any]]:
    """
    AI agent that detects conflicts between multiple driver routes
    (e.g., multiple drivers in same area at same time)
    """
    conflicts = []

    for i, route1 in enumerate(routes):
        if not route1.get("orders") or route1.get("status") != "active":
            continue

        for j, route2 in enumerate(routes[i+1:], start=i+1):
            if not route2.get("orders") or route2.get("status") != "active":
                continue

            # Check if routes have orders in similar locations
            for order1 in route1.get("orders", []):
                if not order1.get("latitude") or not order1.get("longitude"):
                    continue

                for order2 in route2.get("orders", []):
                    if not order2.get("latitude") or not order2.get("longitude"):
                        continue

                    distance = calculate_distance(
                        order1["latitude"], order1["longitude"],
                        order2["latitude"], order2["longitude"]
                    )

                    if distance < conflict_threshold_km:
                        conflicts.append({
                            "route1_id": route1.get("id"),
                            "route2_id": route2.get("id"),
                            "driver1": route1.get("driver_name"),
                            "driver2": route2.get("driver_name"),
                            "order1_id": order1.get("id"),
                            "order2_id": order2.get("id"),
                            "distance_km": distance,
                            "suggestion": f"Drivers {route1.get('driver_name')} and {route2.get('driver_name')} are within {distance:.2f} km"
                        })

    return conflicts


def analyze_new_order_for_driver(
    new_order: Dict[str, Any],
    driver_location: Dict[str, float],
    current_route: List[Dict[str, Any]],
    max_detour_km: float = 5.0
) -> Dict[str, Any]:
    """
    AI agent that analyzes if a new order should be added to a driver's route
    """
    if not new_order.get("latitude") or not new_order.get("longitude"):
        return {
            "can_add": False,
            "reason": "Order missing location data"
        }

    # Calculate distance from driver to new order
    distance_to_order = calculate_distance(
        driver_location["lat"], driver_location["lon"],
        new_order["latitude"], new_order["longitude"]
    )

    # Calculate distance from new order to next stop in route
    detour_distance = 0.0
    if current_route:
        next_stop = current_route[0]
        if next_stop.get("latitude") and next_stop.get("longitude"):
            # Distance: driver -> new_order -> next_stop
            distance_driver_to_new = distance_to_order
            distance_new_to_next = calculate_distance(
                new_order["latitude"], new_order["longitude"],
                next_stop["latitude"], next_stop["longitude"]
            )
            distance_driver_to_next = calculate_distance(
                driver_location["lat"], driver_location["lon"],
                next_stop["latitude"], next_stop["longitude"]
            )
            detour_distance = (distance_driver_to_new + distance_new_to_next) - distance_driver_to_next

    can_add = distance_to_order <= max_detour_km and detour_distance <= max_detour_km

    suggestion = ""
    if can_add:
        suggestion = f"Order is {distance_to_order:.2f} km away. Detour: {detour_distance:.2f} km"
    else:
        suggestion = f"Order is too far ({distance_to_order:.2f} km) or detour too large ({detour_distance:.2f} km)"

    return {
        "can_add": can_add,
        "distance_to_order_km": distance_to_order,
        "detour_distance_km": detour_distance,
        "suggestion": suggestion,
        "recommended_insertion_index": 0 if can_add else None
    }


def generate_route_summary(route: Dict[str, Any]) -> str:
    """
    Generate a human-readable summary of a route using AI
    """
    if GEMINI_AVAILABLE:
        try:
            import os
            api_key = os.getenv('GEMINI_API_KEY')
            if api_key:
                genai.configure(api_key=api_key)
                model = genai.GenerativeModel('gemini-2.5-flash')

                prompt = f"""Generate a brief, helpful summary for a delivery driver about their route.

Route details:
- Driver: {route.get('driver_name', 'Unknown')}
- Number of stops: {len(route.get('orders', []))}
- Status: {route.get('status', 'unknown')}

Generate a friendly, concise summary (2-3 sentences) that helps the driver understand their route."""

                response = model.generate_content(prompt)
                return response.text.strip()
        except Exception as e:
            print(f"Error generating Gemini summary: {e}")

    # Fallback to simple summary
    num_stops = len(route.get('orders', []))
    return f"Route with {num_stops} delivery stops. Status: {route.get('status', 'planned')}"
