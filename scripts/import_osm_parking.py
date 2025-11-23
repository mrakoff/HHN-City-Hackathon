#!/usr/bin/env python3
"""
Fetch parking-related street segments from Overpass (per gptsays2.txt) and
materialize them as discrete parking points inside the local database.

Workflow:
1. Query Baden-Württemberg (area id 3600061477) for parking ways / lanes.
2. Generate points every ~10 meters along each way.
3. Upsert the generated points into the parking_locations table.
"""

import argparse
import json
import os
import sys
from typing import Iterable, List

# Ensure backend modules can be imported when running from repo root
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from backend.database import ParkingLocation, SessionLocal  # noqa: E402
from backend.services.parking_osm import (  # noqa: E402
    OSM_STATE_AREA_ID,
    PARKING_WAY_TAGS,
    fetch_osm_parking_segments,
    generate_parking_points_from_segments,
)


def chunked(iterable: List[dict], size: int) -> Iterable[List[dict]]:
    for idx in range(0, len(iterable), size):
        yield iterable[idx: idx + size]


def persist_points(points: List[dict], batch_size: int, clear_existing: bool) -> int:
    session = SessionLocal()
    inserted = 0
    try:
        if clear_existing:
            deleted = session.query(ParkingLocation).delete()
            session.commit()
            print(f"🧹 Cleared {deleted} existing parking location(s)")

        for batch in chunked(points, batch_size):
            payload = []
            for point in batch:
                notes = {
                    "source": point.get("source"),
                    "osm_way_id": point.get("way_id"),
                    "point_index": point.get("point_index"),
                    "distance_from_start_m": point.get("distance_meters"),
                    "tags": point.get("tags"),
                }
                payload.append(
                    ParkingLocation(
                        name=point.get("name"),
                        address=point.get("address")
                        or f"OSM parking {point['latitude']:.5f},{point['longitude']:.5f}",
                        latitude=point["latitude"],
                        longitude=point["longitude"],
                        notes=json.dumps(notes, ensure_ascii=False),
                    )
                )

            session.bulk_save_objects(payload)
            session.commit()
            inserted += len(payload)
            print(f"💾 Stored {inserted}/{len(points)} parking points...", end="\r")

        session.commit()
        print()  # newline after progress updates
    except Exception as exc:  # pragma: no cover - CLI utility
        session.rollback()
        raise RuntimeError(f"Failed to persist parking points: {exc}") from exc
    finally:
        session.close()

    return inserted


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Import Baden-Württemberg parking lanes into the local DB"
    )
    parser.add_argument(
        "--area-id",
        type=int,
        default=OSM_STATE_AREA_ID,
        help="OSM area id to query (default: Baden-Württemberg 3600061477)",
    )
    parser.add_argument(
        "--spacing-m",
        type=float,
        default=10.0,
        help="Distance in meters between generated parking points (default: 10m)",
    )
    parser.add_argument(
        "--max-ways",
        type=int,
        default=None,
        help="Optional cap on number of ways processed (debugging)",
    )
    parser.add_argument(
        "--max-points",
        type=int,
        default=None,
        help="Optional cap on number of points generated (debugging)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=500,
        help="Number of parking rows inserted per transaction (default: 500)",
    )
    parser.add_argument(
        "--clear-existing",
        action="store_true",
        help="Delete existing entries from parking_locations before import",
    )
    parser.add_argument(
        "--dedupe-decimals",
        type=int,
        default=5,
        help="Round coordinates to this precision when deduplicating (default: 5)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    print("🚗 Fetching OSM parking ways via Overpass (Option A)...")
    segments = fetch_osm_parking_segments(area_id=args.area_id, tags=PARKING_WAY_TAGS)
    if args.max_ways:
        segments = segments[: args.max_ways]
    print(f"   → Retrieved {len(segments)} parking-tagged way(s)")

    print(f"🛠️  Generating parking points every ~{args.spacing_m} m...")
    points = generate_parking_points_from_segments(
        segments,
        spacing_meters=args.spacing_m,
        dedupe_decimals=args.dedupe_decimals,
        max_points=args.max_points,
    )
    print(f"   → Generated {len(points)} parking coordinate(s)")

    if not points:
        print("⚠️  No parking points generated; aborting.")
        return

    print("🗂️  Persisting into parking_locations table...")
    inserted = persist_points(
        points,
        batch_size=args.batch_size,
        clear_existing=args.clear_existing,
    )
    print(f"✅ Done! Stored {inserted} parking point(s).")


if __name__ == "__main__":  # pragma: no cover - CLI utility
    main()
