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

# OSRM server URL (default: localhost:5000)
OSRM_BASE_URL = os.getenv("OSRM_BASE_URL", "http://localhost:5000")
OSRM_ENABLED = os.getenv("OSRM_ENABLED", "true").lower() == "true"


class OSRMError(Exception):
    """Custom exception for OSRM-related errors"""
    pass


def check_osrm_available() -> bool:
    """Check if OSRM server is available"""
    if not OSRM_ENABLED:
        return False

    try:
        response = requests.get(f"{OSRM_BASE_URL}/route/v1/driving/9.21,48.78;9.18,48.77?overview=false", timeout=2)
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
        # Build coordinate string
        coords = ";".join([f"{w['lon']},{w['lat']}" for w in waypoints])
        url = f"{OSRM_BASE_URL}/route/v1/{profile}/{coords}"

        params = {
            "overview": "full",
            "geometries": "geojson"
        }

        response = requests.get(url, params=params, timeout=10)

        if response.status_code != 200:
            return None

        data = response.json()

        if data.get("code") != "Ok" or not data.get("routes"):
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
