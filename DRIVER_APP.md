# Driver Companion Interface

This repository now ships with a lightweight driver-facing experience that keeps couriers in sync with dispatch, routes, and proof-of-delivery capture.

## Where to access it

- Start the FastAPI backend (`uvicorn backend.main:app --reload`).
- Open `http://localhost:8000/driver` in any modern browser. The React app is bundled via CDN + Babel so no build step is required.

## Driver authentication

- Every driver record now has an `access_code` column (`drivers.access_code`).
- Codes are generated automatically when seeding via `scripts/setup_database.py` or creating a driver through the API (`POST /api/drivers`).
- All driver-only endpoints expect the header `X-Driver-Code: <driver access code>`.
- For local troubleshooting you can enable the (off by default) query parameter fallback by setting `ALLOW_DRIVER_TEST_MODE=1` before starting the API. **Do not enable this in production.**

## New backend endpoints

| Endpoint | Method | Description |
| --- | --- | --- |
| `/api/orders/driver/orders` | GET | Lists all active orders assigned to the authenticated driver (set `?include_completed=true` to fetch history). |
| `/api/orders/driver/orders/{order_id}` | GET | Returns assignment detail (route metadata + order payload) for a single stop. |
| `/api/orders/driver/orders/{order_id}/status` | POST (JSON) | Update driver-facing status, notes, optional failure reason, and GPS coordinates. |
| `/api/orders/driver/orders/{order_id}/proof` | POST (multipart) | Upload delivery photo(s), signature (image upload or base64 canvas), optional notes + GPS. Marks the order as delivered when successful. |

### File storage

- Proof assets are persisted beneath `uploads/proof/` by default.
- Override this location via `PROOF_UPLOAD_DIR=/absolute/path/to/storage`.

## Frontend capabilities

- Secure login via driver access code (stored in `localStorage` for convenience).
- Always-on order feed with 60s auto-refresh + manual sync.
- One-click status updates (accepted, en_route, arrived, delivered, failed) with optional GPS capture.
- Proof workflow supporting camera uploads, signature pad, geotagging, and contextual notes.
- Responsive UI tuned for phones and tablets.

## Shared frontend utilities

- `frontend/shared/config.js` exposes `window.__HHN_API_BASE`.
- `frontend/shared/apiClient.js` provides a thin wrapper around `fetch` (JSON + multipart helpers used by the driver app, and available to the planner UI if desired).

## Testing

```
pytest backend/tests/test_driver_endpoints.py
```

The tests spin up an isolated SQLite database and assert:

- Driver token enforcement.
- Listing assigned orders.
- Status updates (notes + GPS persistence).
- Proof uploads (signature-only scenario, metadata persistence, file written to disk).

## Seeding and mock data

`./scripts/setup_database.py` now assigns seeded orders to drivers and prints each driver's generated token so you can log into the driver UI immediately.

Mock document generation (`scripts/generate_mock_orders.py`) now embeds driver + proof placeholders to keep parity with the new data model.
