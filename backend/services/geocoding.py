import requests
from typing import Optional, Dict
import time

# Rate limiting for Nominatim (free service)
_last_request_time = 0
_min_request_interval = 1.0  # 1 second between requests


def geocode_address(address: str) -> Optional[Dict[str, float]]:
    """
    Geocode an address using Nominatim (OpenStreetMap)
    Returns dict with 'lat' and 'lon' or None if not found
    """
    global _last_request_time

    # Rate limiting
    current_time = time.time()
    time_since_last = current_time - _last_request_time
    if time_since_last < _min_request_interval:
        time.sleep(_min_request_interval - time_since_last)

    try:
        url = "https://nominatim.openstreetmap.org/search"
        params = {
            "q": address,
            "format": "json",
            "limit": 1
        }
        headers = {
            "User-Agent": "RoutePlanningApp/1.0"
        }

        response = requests.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()

        data = response.json()
        if data and len(data) > 0:
            result = data[0]
            _last_request_time = time.time()
            return {
                "lat": float(result["lat"]),
                "lon": float(result["lon"])
            }

        return None

    except Exception as e:
        print(f"Error geocoding address '{address}': {e}")
        return None


def reverse_geocode(lat: float, lon: float) -> Optional[str]:
    """
    Reverse geocode coordinates to address
    """
    global _last_request_time

    # Rate limiting
    current_time = time.time()
    time_since_last = current_time - _last_request_time
    if time_since_last < _min_request_interval:
        time.sleep(_min_request_interval - time_since_last)

    try:
        url = "https://nominatim.openstreetmap.org/reverse"
        params = {
            "lat": lat,
            "lon": lon,
            "format": "json"
        }
        headers = {
            "User-Agent": "RoutePlanningApp/1.0"
        }

        response = requests.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()

        data = response.json()
        if data and "display_name" in data:
            _last_request_time = time.time()
            return data["display_name"]

        return None

    except Exception as e:
        print(f"Error reverse geocoding coordinates ({lat}, {lon}): {e}")
        return None
