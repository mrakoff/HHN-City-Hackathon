"""
OSRM (Open Source Routing Machine) client for real road-based routing.

This service provides accurate road distances, travel times, and route geometry
by querying a local OSRM server.

Setup:
1. Download OSM data: wget https://download.geofabrik.de/europe/germany/baden-wuerttemberg-latest.osm.pbf
2. Extract: docker run -t -v $(pwd):/data osrm/osrm-backend osrm-extract -p /opt/car.lua /data/baden-wuerttemberg-latest.osm.pbf
3. Partition: docker run -t -v $(pwd):/data osrm/osrm-backend osrm-partition /data/baden-wuerttemberg-latest.osrm
4. Customize: docker run -t -v $(pwd):/data osrm/osrm-backend osrm-customize /data/baden-wuerttemberg-latest.osrm
5. Run server: docker run -t -i -p 5000:5000 -v $(pwd):/data osrm/osrm-backend osrm-routed --algorithm mld /data/baden-wuerttemberg-latest.osrm
"""

from typing import List, Dict, Tuple, Optional, Any
import os
import requests
from datetime import timedelta
import logging

# Load environment variables if dotenv is available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logger = logging.getLogger(__name__)

# OSRM server URL (default: localhost:5001)
OSRM_BASE_URL = os.getenv("OSRM_BASE_URL", "http://localhost:5001")
OSRM_ENABLED = os.getenv("OSRM_ENABLED", "true").lower() == "true"


class OSRMError(Exception):
    """Custom exception for OSRM-related errors"""
    pass


def check_osrm_available() -> bool:
    """Check if OSRM server is available"""
    if not OSRM_ENABLED:
        return False

    try:
        # Use a simple nearest request to check availability
        response = requests.get(f"{OSRM_BASE_URL}/nearest/v1/driving/9.1817,48.7833", timeout=2)
        return response.status_code == 200
    except Exception as e:
        logger.debug(f"OSRM server not available: {e}")
        return False


def get_route(
    start_lat: float,
    start_lon: float,
    end_lat: float,
    end_lon: float,
    profile: str = "driving",
    overview: str = "full",
    geometries: str = "geojson",
    steps: bool = False
) -> Optional[Dict[str, Any]]:
    """
    Get route between two points using OSRM

    Args:
        start_lat: Starting latitude
        start_lon: Starting longitude
        end_lat: Ending latitude
        end_lon: Ending longitude
        profile: Routing profile (driving, walking, cycling)
        overview: Route overview level (simplified, full, false)
        geometries: Geometry format (polyline, polyline6, geojson)
        steps: Include turn-by-turn instructions

    Returns:
        Route data dict with distance (meters), duration (seconds), and geometry
        Returns None if OSRM is unavailable or route not found
    """
    if not OSRM_ENABLED or not check_osrm_available():
        return None

    try:
        # OSRM format: lon,lat (note: longitude first!)
        coordinates = f"{start_lon},{start_lat};{end_lon},{end_lat}"
        url = f"{OSRM_BASE_URL}/route/v1/{profile}/{coordinates}"

        params = {
            "overview": overview,
            "geometries": geometries,
            "steps": "true" if steps else "false"
        }

        response = requests.get(url, params=params, timeout=5)

        if response.status_code != 200:
            logger.warning(f"OSRM route request failed: {response.status_code}")
            return None

        data = response.json()

        if data.get("code") != "Ok" or not data.get("routes"):
            logger.warning(f"OSRM route not found: {data.get('code')}")
            return None

        route = data["routes"][0]

        return {
            "distance": route["distance"],  # meters
            "duration": route["duration"],  # seconds
            "geometry": route.get("geometry"),  # GeoJSON or polyline
            "legs": route.get("legs", []),
            "steps": route.get("steps", []) if steps else []
        }

    except requests.exceptions.RequestException as e:
        logger.warning(f"OSRM request error: {e}")
        return None
    except Exception as e:
        logger.error(f"OSRM error: {e}")
        return None


def get_route_distance_and_time(
    start_lat: float,
    start_lon: float,
    end_lat: float,
    end_lon: float,
    profile: str = "driving"
) -> Tuple[Optional[float], Optional[float]]:
    """
    Get distance (km) and time (minutes) between two points

    Returns:
        Tuple of (distance_km, time_minutes) or (None, None) if unavailable
    """
    route = get_route(start_lat, start_lon, end_lat, end_lon, profile, overview="false")

    if not route:
        return None, None

    distance_km = route["distance"] / 1000.0  # Convert meters to km
    time_minutes = route["duration"] / 60.0  # Convert seconds to minutes

    return distance_km, time_minutes


def get_table(
    sources: List[Tuple[float, float]],
    destinations: Optional[List[Tuple[float, float]]] = None,
    profile: str = "driving"
) -> Optional[List[List[float]]]:
    """
    Get distance/duration table between multiple points (distance matrix)

    Args:
        sources: List of (lat, lon) tuples for source points
        destinations: List of (lat, lon) tuples for destination points (default: same as sources)
        profile: Routing profile

    Returns:
        2D list where table[i][j] = distance from sources[i] to destinations[j] (in meters)
        Returns None if OSRM is unavailable
    """
    if not OSRM_ENABLED or not check_osrm_available():
        return None

    if destinations is None:
        destinations = sources

    try:
        # Build coordinate string: lon,lat;lon,lat;...
        # OSRM format: sources first, then destinations
        all_coords = sources + destinations
        coord_string = ";".join([f"{lon},{lat}" for lat, lon in all_coords])

        url = f"{OSRM_BASE_URL}/table/v1/{profile}/{coord_string}"

        params = {
            "sources": ";".join([str(i) for i in range(len(sources))]),
            "destinations": ";".join([str(len(sources) + i) for i in range(len(destinations))])
        }

        response = requests.get(url, params=params, timeout=10)

        if response.status_code != 200:
            logger.warning(f"OSRM table request failed: {response.status_code}")
            return None

        data = response.json()

        if data.get("code") != "Ok":
            logger.warning(f"OSRM table not found: {data.get('code')}")
            return None

        # Return distance matrix (in meters)
        return data.get("distances", [])

    except requests.exceptions.RequestException as e:
        logger.warning(f"OSRM table request error: {e}")
        return None
    except Exception as e:
        logger.error(f"OSRM table error: {e}")
        return None


def get_route_geometry(
    waypoints: List[Dict[str, float]],
    profile: str = "driving"
) -> Optional[Dict[str, Any]]:
    """
    Get route geometry for multiple waypoints

    Args:
        waypoints: List of dicts with 'lat' and 'lon' keys
        profile: Routing profile

    Returns:
        Route data with geometry (GeoJSON) or None
    """
    if not waypoints or len(waypoints) < 2:
        return None

    if not OSRM_ENABLED or not check_osrm_available():
        return None

    try:
        # First, snap all waypoints to nearest roads
        snapped_waypoints = []
        for waypoint in waypoints:
            road_point = find_nearest_road_point(waypoint["lat"], waypoint["lon"], profile)
            if road_point:
                snapped_waypoints.append({
                    "lat": road_point["latitude"],
                    "lon": road_point["longitude"]
                })
            else:
                # If we can't snap to a road, use the original coordinates
                snapped_waypoints.append(waypoint)

        # Build coordinate string using snapped coordinates
        coords = ";".join([f"{w['lon']},{w['lat']}" for w in snapped_waypoints])
        url = f"{OSRM_BASE_URL}/route/v1/{profile}/{coords}"

        params = {
            "overview": "full",
            "geometries": "geojson"
        }

        response = requests.get(url, params=params, timeout=10)

        if response.status_code != 200:
            logger.warning(f"OSRM geometry request failed: {response.status_code}")
            return None

        data = response.json()

        if data.get("code") != "Ok" or not data.get("routes"):
            logger.warning(f"OSRM geometry not found: {data.get('code')}")
            return None

        route = data["routes"][0]

        return {
            "distance": route["distance"],  # meters
            "duration": route["duration"],  # seconds
            "geometry": route.get("geometry"),  # GeoJSON LineString
            "waypoints": data.get("waypoints", [])
        }

    except Exception as e:
        logger.warning(f"OSRM geometry error: {e}")
        return None


def find_nearest_road_point(
    lat: float,
    lon: float,
    profile: str = "driving"
) -> Optional[Dict[str, Any]]:
    """
    Find the nearest point on a road to the given coordinates using OSRM nearest service

    Args:
        lat: Latitude
        lon: Longitude
        profile: Routing profile (driving, walking, cycling)

    Returns:
        Dict with 'latitude', 'longitude', and 'distance' (meters) to nearest road point
        Returns None if OSRM is unavailable
    """
    if not OSRM_ENABLED or not check_osrm_available():
        return None

    try:
        url = f"{OSRM_BASE_URL}/nearest/v1/{profile}/{lon},{lat}"
        response = requests.get(url, timeout=5)

        if response.status_code != 200:
            logger.warning(f"OSRM nearest request failed: {response.status_code}")
            return None

        data = response.json()

        if data.get("code") != "Ok" or not data.get("waypoints"):
            return None

        waypoint = data["waypoints"][0]
        location = waypoint["location"]

        return {
            "latitude": location[1],  # OSRM returns [lon, lat]
            "longitude": location[0],
            "distance": waypoint.get("distance", 0)  # meters
        }

    except Exception as e:
        logger.warning(f"OSRM nearest error: {e}")
        return None


def find_street_parking_near_delivery(
    delivery_lat: float,
    delivery_lon: float,
    target_distance_km: float = 0.5,
    num_candidates: int = 8
) -> Optional[Dict[str, Any]]:
    """
    Find a street parking location approximately target_distance_km away from delivery

    Generates candidate points in a circle around delivery, then snaps them to nearest roads

    Args:
        delivery_lat: Delivery location latitude
        delivery_lon: Delivery location longitude
        target_distance_km: Target distance from delivery (default: 0.5 km)
        num_candidates: Number of candidate points to try (default: 8)

    Returns:
        Dict with parking location (lat, lon) snapped to nearest road, or None
    """
    import math

    if not OSRM_ENABLED or not check_osrm_available():
        return None

    R = 6371  # Earth radius in km

    best_parking = None
    best_distance_diff = float('inf')

    # Generate candidate points in a circle around delivery
    for i in range(num_candidates):
        # Angle in radians
        angle = (2 * math.pi * i) / num_candidates

        # Calculate candidate point at target_distance_km from delivery
        lat_rad = math.radians(delivery_lat)
        lon_rad = math.radians(delivery_lon)

        candidate_lat = math.asin(
            math.sin(lat_rad) * math.cos(target_distance_km / R) +
            math.cos(lat_rad) * math.sin(target_distance_km / R) * math.cos(angle)
        )
        candidate_lon = lon_rad + math.atan2(
            math.sin(angle) * math.sin(target_distance_km / R) * math.cos(lat_rad),
            math.cos(target_distance_km / R) - math.sin(lat_rad) * math.sin(candidate_lat)
        )

        candidate_lat = math.degrees(candidate_lat)
        candidate_lon = math.degrees(candidate_lon)

        # Snap to nearest road
        road_point = find_nearest_road_point(candidate_lat, candidate_lon)
        if not road_point:
            continue

        # Calculate actual distance from delivery to snapped road point
        # Use Haversine formula for distance calculation
        lat1_rad = math.radians(delivery_lat)
        lat2_rad = math.radians(road_point["latitude"])
        dlat = lat2_rad - lat1_rad
        dlon = math.radians(road_point["longitude"] - delivery_lon)

        a = (math.sin(dlat / 2) ** 2 +
             math.cos(lat1_rad) * math.cos(lat2_rad) *
             math.sin(dlon / 2) ** 2)
        c = 2 * math.asin(math.sqrt(a))
        actual_distance = R * c

        # Find candidate closest to target distance
        distance_diff = abs(actual_distance - target_distance_km)
        if distance_diff < best_distance_diff:
            best_distance_diff = distance_diff
            best_parking = {
                "latitude": road_point["latitude"],
                "longitude": road_point["longitude"],
                "distance_km": actual_distance,
                "name": f"Street parking ({actual_distance:.2f} km away)"
            }

    return best_parking
