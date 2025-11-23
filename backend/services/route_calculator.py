from typing import List, Dict, Tuple, Optional, Any
from datetime import datetime, timedelta
import math
import logging

# Try to import OSRM client
try:
    from .osrm_client import get_route_distance_and_time, get_route_geometry, check_osrm_available
    OSRM_AVAILABLE = True
except ImportError:
    OSRM_AVAILABLE = False

# Try to import OSM parking helper
try:
    from .parking_osm import fetch_osm_parking_nearby
    OSM_PARKING_AVAILABLE = True
except ImportError:
    OSM_PARKING_AVAILABLE = False

logger = logging.getLogger(__name__)


def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate distance between two points using Haversine formula
    Returns distance in kilometers
    """
    R = 6371  # Earth radius in kilometers

    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)

    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2) ** 2)

    c = 2 * math.asin(math.sqrt(a))
    distance = R * c

    return distance


def estimate_travel_time(distance_km: float, avg_speed_kmh: float = 50) -> float:
    """
    Estimate travel time in minutes
    """
    if distance_km <= 0:
        return 0

    time_hours = distance_km / avg_speed_kmh
    time_minutes = time_hours * 60

    # Add buffer for city driving (traffic, stops, etc.)
    buffer_multiplier = 1.3
    return time_minutes * buffer_multiplier


def calculate_route_distance(route_points: List[Dict[str, float]]) -> Tuple[float, float]:
    """
    Calculate total distance and time for a route
    Uses OSRM if available for accurate road-based routing, falls back to Haversine

    route_points: List of dicts with 'lat' and 'lon' keys

    Returns: (total_distance_km, total_time_minutes)
    """
    if len(route_points) < 2:
        return 0.0, 0.0

    # Try OSRM first for accurate road-based routing
    if OSRM_AVAILABLE and check_osrm_available():
        try:
            # Get route geometry for entire waypoint sequence
            route_data = get_route_geometry(route_points)
            if route_data:
                distance_km = route_data["distance"] / 1000.0  # Convert meters to km
                time_minutes = route_data["duration"] / 60.0  # Convert seconds to minutes
                return distance_km, time_minutes
        except Exception as e:
            logger.warning(f"OSRM route calculation failed, using fallback: {e}")

    # Fallback to Haversine (straight-line) distance
    total_distance = 0.0
    for i in range(len(route_points) - 1):
        point1 = route_points[i]
        point2 = route_points[i + 1]
        distance = calculate_distance(
            point1['lat'], point1['lon'],
            point2['lat'], point2['lon']
        )
        total_distance += distance

    total_time = estimate_travel_time(total_distance)

    return total_distance, total_time


def calculate_route_metrics(
    route_points: List[Dict[str, float]]
) -> Dict[str, float]:
    """
    Calculate route metrics (distance, time) using Haversine formula
    """
    distance, time = calculate_route_distance(route_points)
    return {
        "distance_km": distance,
        "time_minutes": time
    }


def find_nearest_parking(
    delivery_lat: float,
    delivery_lon: float,
    parking_locations: List[Dict[str, Any]] = None,
    max_distance_km: float = 2.0,
    use_dynamic_parking: bool = True,
    target_parking_distance_km: float = 0.5
) -> Optional[Dict[str, Any]]:
    """
    Find the nearest parking spot to a delivery address.
    Preference order:
      1. Locally cached parking locations (seeded from Overpass)
      2. OSM parking amenities (direct Overpass nearby query)
      3. Dynamic street parking via OSRM (if enabled)
    """

    def pick_best(candidates: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        best = None
        best_distance = float("inf")
        for candidate in candidates:
            lat = candidate.get("latitude")
            lon = candidate.get("longitude")
            if lat is None or lon is None:
                continue
            distance = calculate_distance(delivery_lat, delivery_lon, lat, lon)
            if distance < best_distance and distance <= max_distance_km:
                best_distance = distance
                best = {
                    **candidate,
                    "distance_km": distance
                }
        return best

    # 1) Locally cached parking dataset (populated via scripts/import_osm_parking.py)
    if parking_locations:
        best_local = pick_best(parking_locations)
        if best_local:
            best_local.setdefault("source", best_local.get("source") or "db")
            return best_local

    # 2) OSM parking data (live Overpass fallback if local cache misses)
    if OSM_PARKING_AVAILABLE:
        try:
            osm_candidates = fetch_osm_parking_nearby(delivery_lat, delivery_lon)
            best_osm = pick_best(osm_candidates)
            if best_osm:
                best_osm.setdefault("source", "osm")
                return best_osm
        except Exception as exc:
            logger.debug(f"OSM parking lookup failed: {exc}")

    # 3) Dynamic parking via OSRM
    if use_dynamic_parking:
        try:
            from .osrm_client import find_street_parking_near_delivery
            dynamic_parking = find_street_parking_near_delivery(
                delivery_lat,
                delivery_lon,
                target_distance_km=target_parking_distance_km
            )
            if dynamic_parking:
                dynamic_parking.setdefault("source", "osrm")
                return dynamic_parking
        except Exception as exc:
            logger.debug(f"Dynamic parking failed, falling back to static: {exc}")

    # 3) Static parking entries
    if parking_locations:
        best_static = pick_best(parking_locations)
        if best_static:
            best_static.setdefault("source", "static")
            return best_static

    return None


def build_route_with_parking(
    depot: Dict[str, float],
    orders: List[Dict[str, Any]],
    parking_locations: List[Dict[str, Any]],
    max_parking_distance_km: float = 2.0
) -> Dict[str, Any]:
    """
    Build a route with parking spots included
    Route structure: depot → parking1 → delivery1 → parking2 → delivery2 → ... → depot

    Args:
        depot: Dict with 'lat' and 'lon' keys
        orders: List of order dicts with 'lat', 'lon', and optionally 'id' keys
        parking_locations: List of parking location dicts with 'latitude' and 'longitude' keys
        max_parking_distance_km: Maximum distance from delivery to parking spot

    Returns:
        Dict with:
            - waypoints: List of waypoint dicts with type (depot/parking/delivery), coordinates, and metadata
            - total_distance_km: Total route distance
            - total_time_minutes: Total estimated travel time
    """
    waypoints = []

    # Start at depot
    waypoints.append({
        "type": "depot",
        "lat": depot["lat"],
        "lon": depot["lon"],
        "metadata": depot
    })

    # For each order, add parking → delivery
    for order in orders:
        delivery_lat = order.get("lat") or order.get("latitude")
        delivery_lon = order.get("lon") or order.get("longitude")

        if not delivery_lat or not delivery_lon:
            continue

        # Find nearest parking spot (use dynamic parking by default, 0.5km away)
        parking = find_nearest_parking(
            delivery_lat,
            delivery_lon,
            parking_locations,
            max_parking_distance_km,
            use_dynamic_parking=True,
            target_parking_distance_km=0.5
        )

        # Add parking spot (if found)
        if parking:
            waypoints.append({
                "type": "parking",
                "lat": parking["latitude"],
                "lon": parking["longitude"],
                "metadata": parking,
                "distance_to_delivery_km": parking.get("distance_km", 0)
            })

        # Add delivery location
        waypoints.append({
            "type": "delivery",
            "lat": delivery_lat,
            "lon": delivery_lon,
            "metadata": order
        })

    # Return to depot
    waypoints.append({
        "type": "depot",
        "lat": depot["lat"],
        "lon": depot["lon"],
        "metadata": depot
    })

    # Calculate route metrics (uses OSRM if available)
    route_points = [{"lat": w["lat"], "lon": w["lon"]} for w in waypoints]
    total_distance, total_time = calculate_route_distance(route_points)

    # Get route geometry if OSRM is available (for map display)
    route_geometry = None
    if OSRM_AVAILABLE and check_osrm_available():
        try:
            logger.info(f"Attempting to get OSRM geometry for {len(route_points)} waypoints")
            route_data = get_route_geometry(route_points)
            if route_data and route_data.get("geometry"):
                route_geometry = route_data["geometry"]
                logger.info("Successfully obtained OSRM route geometry")
            else:
                logger.warning("OSRM returned no geometry - will use straight-line fallback")
        except Exception as e:
            logger.warning(f"Could not get route geometry from OSRM: {e} - will use straight-line fallback")

    result = {
        "waypoints": waypoints,
        "total_distance_km": total_distance,
        "total_time_minutes": total_time
    }

    if route_geometry:
        result["geometry"] = route_geometry  # GeoJSON LineString for map display

    return result


def calculate_complete_route(
    depot: Dict[str, Any],
    orders: List[Dict[str, Any]],
    parking_locations: List[Dict[str, Any]],
    optimized_order_indices: Optional[List[int]] = None,
    start_time: Optional[datetime] = None
) -> Dict[str, Any]:
    """
    Calculate a complete route with depot, parking spots, and deliveries
    Includes optimization and estimated arrival times

    Args:
        depot: Depot dict with 'latitude' and 'longitude' keys
        orders: List of order dicts with 'lat'/'latitude' and 'lon'/'longitude' keys
        parking_locations: List of parking location dicts
        optimized_order_indices: Optional pre-optimized order sequence (if None, orders used as-is)
        start_time: Optional datetime for calculating arrival times

    Returns:
        Dict with:
            - waypoints: Complete route waypoints with types and metadata
            - total_distance_km: Total route distance
            - total_time_minutes: Total estimated travel time
            - estimated_arrival_times: List of estimated arrival times for each waypoint
            - optimized_order_sequence: Order sequence used
    """
    # Normalize depot coordinates
    depot_coords = {
        "lat": depot.get("lat") or depot.get("latitude"),
        "lon": depot.get("lon") or depot.get("longitude")
    }

    if not depot_coords["lat"] or not depot_coords["lon"]:
        raise ValueError("Depot must have valid latitude and longitude")

    # Normalize order coordinates
    normalized_orders = []
    for order in orders:
        lat = order.get("lat") or order.get("latitude")
        lon = order.get("lon") or order.get("longitude")
        if lat and lon:
            normalized_orders.append({
                "lat": lat,
                "lon": lon,
                **order
            })

    if not normalized_orders:
        raise ValueError("No orders with valid coordinates")

    # Use optimized order indices if provided, otherwise use original order
    if optimized_order_indices is not None:
        ordered_orders = [normalized_orders[i] for i in optimized_order_indices]
    else:
        ordered_orders = normalized_orders

    # Build route with parking
    route_result = build_route_with_parking(
        depot_coords,
        ordered_orders,
        parking_locations
    )

    # Calculate estimated arrival times
    estimated_arrival_times = []
    if start_time:
        current_time = start_time
        waypoints = route_result["waypoints"]

        for i in range(len(waypoints) - 1):
            estimated_arrival_times.append(current_time)

            # Calculate travel time to next waypoint
            point1 = waypoints[i]
            point2 = waypoints[i + 1]

            # Try OSRM first for accurate time
            travel_time = None
            if OSRM_AVAILABLE and check_osrm_available():
                try:
                    _, time_min = get_route_distance_and_time(
                        point1["lat"], point1["lon"],
                        point2["lat"], point2["lon"]
                    )
                    if time_min is not None:
                        travel_time = time_min
                except Exception as e:
                    logger.debug(f"OSRM time calculation failed, using fallback: {e}")

            # Fallback to Haversine-based estimation
            if travel_time is None:
                distance = calculate_distance(
                    point1["lat"], point1["lon"],
                    point2["lat"], point2["lon"]
                )
                travel_time = estimate_travel_time(distance)

            current_time += timedelta(minutes=travel_time)

        # Add arrival time for final waypoint (depot)
        estimated_arrival_times.append(current_time)
    else:
        estimated_arrival_times = [None] * len(route_result["waypoints"])

    # Add arrival times to waypoints
    for i, waypoint in enumerate(route_result["waypoints"]):
        waypoint["estimated_arrival"] = estimated_arrival_times[i]

    return {
        **route_result,
        "estimated_arrival_times": estimated_arrival_times,
        "optimized_order_sequence": optimized_order_indices if optimized_order_indices is not None else list(range(len(normalized_orders)))
    }
