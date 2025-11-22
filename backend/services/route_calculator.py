from typing import List, Dict, Tuple, Optional
import math
import requests


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
    route_points: List of dicts with 'lat' and 'lon' keys

    Returns: (total_distance_km, total_time_minutes)
    """
    if len(route_points) < 2:
        return 0.0, 0.0

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


def get_route_from_osrm(
    points: List[Tuple[float, float]],
    profile: str = "driving"
) -> Optional[Dict]:
    """
    Get route from OSRM (Open Source Routing Machine)
    Returns route geometry and distance/time if available
    """
    if len(points) < 2:
        return None

    try:
        # Format coordinates as "lon,lat;lon,lat;..."
        coordinates = ";".join([f"{lon},{lat}" for lat, lon in points])

        url = f"http://router.project-osrm.org/route/v1/{profile}/{coordinates}"
        params = {
            "overview": "false",
            "alternatives": "false",
            "steps": "false"
        }

        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()

        data = response.json()
        if data.get("code") == "Ok" and data.get("routes"):
            route = data["routes"][0]
            return {
                "distance": route["distance"] / 1000,  # Convert to km
                "duration": route["duration"] / 60,  # Convert to minutes
                "geometry": route.get("geometry")
            }

        return None

    except Exception as e:
        print(f"Error getting route from OSRM: {e}")
        return None


def calculate_route_metrics(
    route_points: List[Dict[str, float]],
    use_osrm: bool = False
) -> Dict[str, float]:
    """
    Calculate route metrics (distance, time)
    If use_osrm is True, tries to use OSRM for more accurate routing
    Falls back to Haversine if OSRM fails
    """
    if use_osrm:
        points = [(p['lat'], p['lon']) for p in route_points]
        osrm_result = get_route_from_osrm(points)
        if osrm_result:
            return {
                "distance_km": osrm_result["distance"],
                "time_minutes": osrm_result["duration"]
            }

    # Fallback to Haversine
    distance, time = calculate_route_distance(route_points)
    return {
        "distance_km": distance,
        "time_minutes": time
    }
