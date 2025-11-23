#!/usr/bin/env python3
"""
Seed the API with 50 Baden-Württemberg mock orders using the /api/orders/bulk endpoint.
Existing orders can optionally be deleted before importing the new dataset.
"""

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Tuple

import requests

ADDRESS_DATA: List[Tuple[str, float, float]] = [
    # Heilbronn - City Center and nearby areas
    ("Kiliansplatz 1, 74072 Heilbronn, Germany", 49.1437, 9.2109),
    ("Allee 12, 74076 Heilbronn, Germany", 49.1395, 9.2067),
    ("Crailsheimstraße 45, 74074 Heilbronn, Germany", 49.1478, 9.2156),
    ("Willy-Brandt-Platz 2, 74072 Heilbronn, Germany", 49.1423, 9.2101),
    ("Kaiserstraße 78, 74072 Heilbronn, Germany", 49.1412, 9.2089),
    ("Sülmerstraße 7, 74072 Heilbronn, Germany", 49.1427, 9.2186),
    ("Kaiserstraße 23, 74072 Heilbronn, Germany", 49.1413, 9.2195),
    ("Allee 19, 74072 Heilbronn, Germany", 49.1405, 9.2206),
    ("Fleiner Straße 8, 74072 Heilbronn, Germany", 49.1390, 9.2243),
    ("Karlstraße 18, 74072 Heilbronn, Germany", 49.1384, 9.2203),
    ("Schweinsbergweg 15, 74072 Heilbronn, Germany", 49.1456, 9.2078),
    ("Lohtorstraße 31, 74072 Heilbronn, Germany", 49.1467, 9.2134),
    ("Friedrichstraße 12, 74072 Heilbronn, Germany", 49.1445, 9.2145),
    ("Kirchbrunnenweg 8, 74072 Heilbronn, Germany", 49.1472, 9.2098),
    ("Geschwister-Scholl-Straße 25, 74072 Heilbronn, Germany", 49.1389, 9.2156),
    ("Moltkestraße 44, 74072 Heilbronn, Germany", 49.1378, 9.2132),
    ("Uhlandstraße 17, 74072 Heilbronn, Germany", 49.1398, 9.2111),
    ("Berliner Platz 3, 74072 Heilbronn, Germany", 49.1489, 9.2123),
    ("Bismarckstraße 29, 74072 Heilbronn, Germany", 49.1463, 9.2079),
    ("Schillerstraße 55, 74072 Heilbronn, Germany", 49.1452, 9.2167),
    ("Goethestraße 22, 74072 Heilbronn, Germany", 49.1438, 9.2089),
    ("Heilbronner Straße 67, 74072 Heilbronn, Germany", 49.1409, 9.2178),
    ("Neckartalstraße 33, 74072 Heilbronn, Germany", 49.1487, 9.2145),
    ("Pfühlstraße 14, 74072 Heilbronn, Germany", 49.1376, 9.2098),
    ("Turmstraße 8, 74072 Heilbronn, Germany", 49.1493, 9.2112),
    ("Weinstraße 41, 74072 Heilbronn, Germany", 49.1421, 9.2189),
    ("Marktplatz 6, 74072 Heilbronn, Germany", 49.1447, 9.2123),
    ("Rathausstraße 19, 74072 Heilbronn, Germany", 49.1418, 9.2145),
    ("Klingenberger Straße 52, 74072 Heilbronn, Germany", 49.1397, 9.2087),
    ("Wilh.-Rabe-Straße 11, 74072 Heilbronn, Germany", 49.1482, 9.2096),
    ("Hafenstraße 27, 74072 Heilbronn, Germany", 49.1367, 9.2123),
    ("Brückenstraße 38, 74072 Heilbronn, Germany", 49.1479, 9.2156),
    ("Siemensstraße 4, 74072 Heilbronn, Germany", 49.1388, 9.2178),
    ("Böckinger Straße 89, 74072 Heilbronn, Germany", 49.1498, 9.2134),
    ("Jägerhausstraße 16, 74072 Heilbronn, Germany", 49.1374, 9.2092),
    ("Kunststraße 23, 74072 Heilbronn, Germany", 49.1465, 9.2187),
    ("Werkstraße 7, 74072 Heilbronn, Germany", 49.1403, 9.2118),
    ("Industriestraße 92, 74072 Heilbronn, Germany", 49.1356, 9.2145),
    ("Gewerbestraße 18, 74072 Heilbronn, Germany", 49.1489, 9.2167),
    ("Bahnhofstraße 77, 74072 Heilbronn, Germany", 49.1432, 9.2076),
    ("Poststraße 34, 74072 Heilbronn, Germany", 49.1456, 9.2134),
    ("Schulstraße 51, 74072 Heilbronn, Germany", 49.1398, 9.2189),
    ("Kirchstraße 28, 74072 Heilbronn, Germany", 49.1473, 9.2101),
    ("Bergstraße 13, 74072 Heilbronn, Germany", 49.1419, 9.2167),
    ("Talstraße 46, 74072 Heilbronn, Germany", 49.1368, 9.2098),
    ("Parkstraße 9, 74072 Heilbronn, Germany", 49.1492, 9.2123),
    ("Ringstraße 72, 74072 Heilbronn, Germany", 49.1387, 9.2156),
    ("Daimlerstraße 21, 74072 Heilbronn, Germany", 49.1448, 9.2089),
    ("Mercedesstraße 35, 74072 Heilbronn, Germany", 49.1423, 9.2178),
    ("Audistraße 12, 74072 Heilbronn, Germany", 49.1379, 9.2112),
    # Tübingen
    ("Neckargasse 10, 72070 Tübingen, Germany", 48.5211, 9.0560),
    ("Holzmarkt 12, 72070 Tübingen, Germany", 48.5217, 9.0576),
    ("Am Markt 5, 72070 Tübingen, Germany", 48.5216, 9.0573),
    ("Karlstraße 3, 72072 Tübingen, Germany", 48.5179, 9.0584),
    ("Derendinger Straße 50, 72072 Tübingen, Germany", 48.5094, 9.0678),
]

def build_order_templates() -> List[Dict[str, Any]]:
    """Return 50 delivery addresses across Baden-Württemberg with coordinates."""
    customers = [
        "Anna Weber",
        "Markus Braun",
        "Sofia Keller",
        "Lukas Fischer",
        "Laura Lehmann",
        "Peter Vogt",
        "Julia Brandt",
        "Jonas Maier",
        "Mara Scholz",
        "David Krämer",
    ]

    descriptions = [
        "Office supplies delivery",
        "Event catering drop-off",
        "Retail restock shipment",
        "Medical supplies delivery",
        "Pharmacy wholesale order",
        "Bakery ingredient refill",
        "Electronics e-commerce order",
        "Furniture sample drop",
        "Grocery restock",
        "Promotional materials shipment",
    ]

    sources = ["email", "phone", "fax", "mail"]
    items_catalog = [
        {"name": "Boxes", "quantity": 4},
        {"name": "Pallet", "quantity": 1},
        {"name": "Crate", "quantity": 2},
        {"name": "Envelope", "quantity": 10},
        {"name": "Parcel", "quantity": 3},
    ]

    templates = []
    now = datetime.now(timezone.utc)
    for idx, (address, latitude, longitude) in enumerate(ADDRESS_DATA, start=1):
        customer = customers[idx % len(customers)]
        description = descriptions[idx % len(descriptions)]
        source = sources[idx % len(sources)]
        window_start = now + timedelta(hours=(idx % 6) + 1)
        window_end = window_start + timedelta(hours=2 + (idx % 3))
        items = [
            items_catalog[idx % len(items_catalog)],
            items_catalog[(idx + 2) % len(items_catalog)]
        ]

        templates.append({
            "delivery_address": address,
            "customer_name": customer,
            "customer_email": f"{customer.split()[0].lower()}{idx}@example.de",
            "customer_phone": f"+49 711 {600000 + idx:07d}",
            "description": description,
            "source": source,
            "priority": ["urgent", "high", "normal", "low"][idx % 4],
            "items": items,
            "delivery_time_window_start": window_start.isoformat(),
            "delivery_time_window_end": window_end.isoformat(),
            "latitude": latitude,
            "longitude": longitude,
        })

    return templates


def delete_existing_orders(api_base: str) -> None:
    response = requests.get(f"{api_base}/orders")
    response.raise_for_status()
    orders = response.json()
    for order in orders:
        order_id = order["id"]
        requests.delete(f"{api_base}/orders/{order_id}").raise_for_status()
        print(f"🗑️  Deleted order {order_id}")


def import_orders(api_base: str, orders: List[Dict[str, Any]]) -> None:
    response = requests.post(f"{api_base}/orders/bulk", json=orders)
    response.raise_for_status()
    created = response.json()
    print(f"✅ Imported {len(created)} orders.")


def main():
    parser = argparse.ArgumentParser(description="Import 50 Baden-Württemberg mock orders")
    parser.add_argument("--api-base", default=os.getenv("API_BASE_URL", "http://localhost:8000/api"),
                        help="Base URL for the API (default: http://localhost:8000/api)")
    parser.add_argument("--clear-existing", action="store_true",
                        help="Delete all existing orders before importing the mock dataset")
    parser.add_argument("--limit", type=int, default=50,
                        help="Number of mock orders to import (max 50)")
    args = parser.parse_args()

    templates = build_order_templates()
    if args.limit < len(templates):
        templates = templates[:args.limit]

    if args.clear_existing:
        print("Clearing existing orders...")
        delete_existing_orders(args.api_base)

    print(f"Importing {len(templates)} mock orders to {args.api_base} ...")
    import_orders(args.api_base, templates)


if __name__ == "__main__":
    try:
        main()
    except requests.HTTPError as exc:
        print(f"❌ HTTP error: {exc.response.status_code} {exc.response.text}")
        sys.exit(1)
    except Exception as exc:
        print(f"❌ Unexpected error: {exc}")
        sys.exit(1)
