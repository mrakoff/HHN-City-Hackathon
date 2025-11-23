import math
import os
import time
import logging
from typing import Dict, Any, Iterable, List, Optional, Set, Tuple

import requests

logger = logging.getLogger(__name__)

OVERPASS_URL = os.getenv("OVERPASS_URL", "https://overpass-api.de/api/interpreter")
OSM_PARKING_ENABLED = os.getenv("OSM_PARKING_ENABLED", "true").lower() == "true"
OSM_PARKING_RADIUS_METERS = int(os.getenv("OSM_PARKING_RADIUS_METERS", "600"))
OSM_PARKING_LIMIT = int(os.getenv("OSM_PARKING_LIMIT", "10"))
OSM_PARKING_CACHE_TTL = int(os.getenv("OSM_PARKING_CACHE_TTL", "300"))

# State-wide extraction defaults (Baden-Württemberg area id per gptsays2.txt)
OSM_STATE_AREA_ID = int(os.getenv("OSM_STATE_AREA_ID", "3600061477"))
OSM_PARKING_POINT_SPACING_METERS = float(
    os.getenv("OSM_PARKING_POINT_SPACING_METERS", "10")
)
OSM_PARKING_DEDUPE_DECIMALS = int(os.getenv("OSM_PARKING_DEDUPE_DECIMALS", "5"))
PARKING_WAY_TAGS = [
    "parking",
    "parking:lane",
    "parking:condition",
    "street_parking",
    "parking:left",
    "parking:right",
    "parking:both",
]

_parking_cache: Dict[str, Any] = {}


def _cache_key(lat: float, lon: float, radius: int) -> str:
    return f"{round(lat, 4)}:{round(lon, 4)}:{radius}"


def fetch_osm_parking_nearby(
    latitude: float,
    longitude: float,
    radius_meters: int = OSM_PARKING_RADIUS_METERS,
    limit: int = OSM_PARKING_LIMIT
) -> List[Dict[str, Any]]:
    """
    Query the Overpass API for parking amenities near the given coordinate.
    Returns a list of parking dicts with lat/lon, name, and metadata.
    """
    if not OSM_PARKING_ENABLED:
        return []

    cache_key = _cache_key(latitude, longitude, radius_meters)
    now = time.time()
    cached = _parking_cache.get(cache_key)
    if cached and cached["expires_at"] > now:
        return cached["data"]

    query = f"""
    [out:json][timeout:25];
    (
        node["amenity"="parking"](around:{radius_meters},{latitude},{longitude});
        way["amenity"="parking"](around:{radius_meters},{latitude},{longitude});
        relation["amenity"="parking"](around:{radius_meters},{latitude},{longitude});
    );
    out center {limit};
    """

    try:
        response = requests.post(
            OVERPASS_URL,
            data={"data": query},
            timeout=30
        )
        response.raise_for_status()
        payload = response.json()
        elements = payload.get("elements", [])

        parks: List[Dict[str, Any]] = []
        for element in elements:
            lat = None
            lon = None

            if element.get("type") == "node":
                lat = element.get("lat")
                lon = element.get("lon")
            elif "center" in element:
                center = element["center"]
                lat = center.get("lat")
                lon = center.get("lon")

            if lat is None or lon is None:
                continue

            tags = element.get("tags", {})
            parks.append({
                "latitude": lat,
                "longitude": lon,
                "name": tags.get("name") or "OSM Parking",
                "address": tags.get("addr:full"),
                "capacity": tags.get("capacity"),
                "source": "osm",
                "osm_id": element.get("id"),
                "tags": tags
            })

            if len(parks) >= limit:
                break

        _parking_cache[cache_key] = {
            "expires_at": now + OSM_PARKING_CACHE_TTL,
            "data": parks
        }

        return parks
    except requests.RequestException as exc:
        logger.warning(f"Overpass parking request failed: {exc}")
        return []


def build_statewide_parking_query(
    area_id: int = OSM_STATE_AREA_ID,
    tags: Optional[Iterable[str]] = None,
    use_bbox: bool = True
) -> str:
    """
    Build Overpass Query fetching parking-related ways across Baden-Württemberg.
    Uses bounding box approach (Baden-Württemberg approximate bounds) if use_bbox=True,
    otherwise uses area relation (may not work if area relation is not available).
    """
    # Baden-Württemberg approximate bounding box
    # lat: 47.5 to 49.8, lon: 7.5 to 10.5
    bbox_south = 47.5
    bbox_north = 49.8
    bbox_west = 7.5
    bbox_east = 10.5

    tag_filters = []
    for tag in (tags or PARKING_WAY_TAGS):
        if use_bbox:
            # Use bounding box query (more reliable than area relation)
            tag_filters.append(f'  way["{tag}"]({bbox_south},{bbox_west},{bbox_north},{bbox_east});')
        else:
            # Use area relation query (original approach)
            tag_filters.append(f'  way["{tag}"](area:{area_id});')

    filters = "\n".join(tag_filters)
    return f"""
    [out:json][timeout:180];
    (
{filters}
    );
    out geom;
    """


def fetch_osm_parking_segments(
    area_id: int = OSM_STATE_AREA_ID,
    tags: Optional[Iterable[str]] = None,
    timeout_seconds: int = 180,
    use_bbox: bool = True
) -> List[Dict[str, Any]]:
    """
    Fetch street segments annotated with parking tags (ways) for the given OSM area.
    This corresponds to the gptsays2.txt "Option A" workflow.
    Uses bounding box by default (more reliable than area relation).
    """
    if not OSM_PARKING_ENABLED:
        logger.info("OSM parking download disabled via OSM_PARKING_ENABLED flag.")
        return []

    query = build_statewide_parking_query(area_id=area_id, tags=tags, use_bbox=use_bbox)
    try:
        response = requests.post(
            OVERPASS_URL,
            data={"data": query},
            timeout=timeout_seconds
        )
        response.raise_for_status()
        payload = response.json()
        return payload.get("elements", [])
    except requests.RequestException as exc:
        logger.error(f"Failed to download parking segments from Overpass: {exc}")
        raise


def _haversine_meters(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
) -> float:
    """Return the distance between two coordinates in meters."""
    radius_km = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.asin(math.sqrt(a))
    return radius_km * c * 1000.0


def _interpolate_points_along_geometry(
    coords: List[Tuple[float, float]],
    targets: List[float],
) -> List[Tuple[float, float, float]]:
    """Interpolate latitude/longitude pairs at the requested distances."""
    if len(coords) < 2:
        lat, lon = coords[0]
        return [(lat, lon, 0.0)]

    # Pre-compute cumulative segment lengths
    segment_lengths: List[float] = []
    for idx in range(len(coords) - 1):
        seg_length = _haversine_meters(
            coords[idx][0],
            coords[idx][1],
            coords[idx + 1][0],
            coords[idx + 1][1],
        )
        segment_lengths.append(seg_length)

    points: List[Tuple[float, float, float]] = []
    accum_length = 0.0
    segment_idx = 0

    for target in targets:
        while (
            segment_idx < len(segment_lengths)
            and accum_length + segment_lengths[segment_idx] < target
        ):
            accum_length += segment_lengths[segment_idx]
            segment_idx += 1

        if segment_idx >= len(segment_lengths):
            lat, lon = coords[-1]
            points.append((lat, lon, target))
            continue

        seg_start = coords[segment_idx]
        seg_end = coords[segment_idx + 1]
        seg_length = segment_lengths[segment_idx]
        if seg_length == 0:
            lat, lon = seg_end
            points.append((lat, lon, target))
            continue

        offset = target - accum_length
        ratio = max(0.0, min(1.0, offset / seg_length))
        lat = seg_start[0] + (seg_end[0] - seg_start[0]) * ratio
        lon = seg_start[1] + (seg_end[1] - seg_start[1]) * ratio
        points.append((lat, lon, target))

    return points


def generate_parking_points_from_segments(
    segments: Iterable[Dict[str, Any]],
    spacing_meters: float = OSM_PARKING_POINT_SPACING_METERS,
    dedupe_decimals: int = OSM_PARKING_DEDUPE_DECIMALS,
    max_points: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Convert OSM parking ways into discrete parking points spaced along the geometry.
    """
    parking_points: List[Dict[str, Any]] = []
    seen: Set[Tuple[float, float]] = set()

    for element in segments:
        if element.get("type") != "way":
            continue
        geometry = element.get("geometry") or []
        if len(geometry) < 2:
            continue

        coords: List[Tuple[float, float]] = [
            (node["lat"], node["lon"])
            for node in geometry
            if "lat" in node and "lon" in node
        ]
        if len(coords) < 2:
            continue

        # Total length of the way
        total_length = 0.0
        for idx in range(len(coords) - 1):
            total_length += _haversine_meters(
                coords[idx][0],
                coords[idx][1],
                coords[idx + 1][0],
                coords[idx + 1][1],
            )

        if total_length == 0:
            continue

        steps = max(1, int(total_length / max(1.0, spacing_meters)))
        targets = [(i / steps) * total_length for i in range(steps + 1)]
        if targets[-1] < total_length:
            targets[-1] = total_length

        interpolated = _interpolate_points_along_geometry(coords, targets)
        tags = element.get("tags", {})
        name = tags.get("name") or "OSM Street Parking"
        base_address = tags.get("addr:full") or tags.get("addr:street")
        way_id = element.get("id")

        for idx, (lat, lon, distance) in enumerate(interpolated):
            key = (round(lat, dedupe_decimals), round(lon, dedupe_decimals))
            if key in seen:
                continue
            seen.add(key)

            parking_points.append({
                "latitude": lat,
                "longitude": lon,
                "name": name,
                "address": base_address or f"OSM parking way {way_id}",
                "source": "osm_overpass_way",
                "way_id": way_id,
                "point_index": idx,
                "distance_meters": distance,
                "tags": tags,
            })

            if max_points and len(parking_points) >= max_points:
                return parking_points

    return parking_points
