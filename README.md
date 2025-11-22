# Route Planning & Logistics System

A comprehensive route planning system for SMEs with multi-driver support, automated order processing, and AI-powered optimization.

## Features

- **Order Management**: Upload and parse orders from email, fax, mail, or phone calls
- **OCR Processing**: Automatically extract order information from scanned documents
- **Multi-Driver Support**: Manage multiple drivers with separate route plans
- **AI Route Optimization**: Optimize routes using OR-Tools or simple algorithms
- **Dynamic Route Updates**: Detect new orders near active drivers and suggest updates
- **Driver Interface**: Mobile-friendly interface for drivers to view routes and provide feedback
- **Location Management**: Manage depots and parking locations

## Technology Stack

- **Backend**: FastAPI (Python)
- **Database**: SQLite
- **Frontend**: Vanilla JavaScript, HTML, CSS
- **Maps**: Leaflet.js with OpenStreetMap
- **Routing**: OSRM (Open Source Routing Machine) - for accurate road-based routing
- **OCR**: Tesseract OCR
- **Route Optimization**: OR-Tools (Google) with OSRM distance matrix
- **Geocoding**: Nominatim (OpenStreetMap)

## Setup

### Prerequisites

- Python 3.8+
- Tesseract OCR installed on your system
  - macOS: `brew install tesseract`
  - Ubuntu: `sudo apt-get install tesseract-ocr`
  - Windows: Download from [GitHub](https://github.com/UB-Mannheim/tesseract/wiki)

### Installation

1. Clone the repository:
```bash
cd HHN-City-Hackathon
```

2. Install Python dependencies:
```bash
pip install -r requirements.txt
```

3. (Optional) Set up OSRM for accurate road-based routing:
   - See [OSRM_SETUP.md](OSRM_SETUP.md) for detailed instructions
   - The system works without OSRM (uses fallback), but OSRM provides much better accuracy

4. (Optional) Set up API keys for advanced features:
```bash
export GEMINI_API_KEY=your_api_key_here  # For AI-powered order parsing
```

5. Initialize the database:
```bash
python -m backend.main
```

6. Start the server:
```bash
uvicorn backend.main:app --reload
```

7. (Optional) Start OSRM server (if using OSRM):
```bash
# See OSRM_SETUP.md for setup instructions
# Or use docker-compose:
docker-compose -f docker-compose.osrm.yml up -d
```

8. Open your browser and navigate to:
```
http://localhost:8000
```

## Usage

### Planner Interface

1. **Add Orders**:
   - Click "Add Order" to manually enter order details
   - Click "Upload Document" to upload scanned orders (PDF, images)
   - Orders are automatically parsed and validated

2. **Manage Drivers**:
   - Add drivers with their contact information
   - Track driver status (available, on_route, offline)

3. **Create Routes**:
   - Create routes and assign orders to drivers
   - Use "Optimize" button to automatically optimize route order
   - View routes on the interactive map

4. **Manage Locations**:
   - Add depots (starting points for routes)
   - Add parking locations for delivery stops

### Driver Interface

Drivers can access a mobile-friendly interface to:
- View their assigned route
- Accept or reject route updates
- Mark orders as completed
- Report problems with deliveries

## API Endpoints

### Orders
- `GET /api/orders` - List all orders
- `POST /api/orders` - Create new order
- `POST /api/orders/upload` - Upload and parse order document
- `POST /api/orders/parse-text` - Parse order from text
- `GET /api/orders/{id}` - Get order details
- `PUT /api/orders/{id}` - Update order
- `DELETE /api/orders/{id}` - Delete order

### Drivers
- `GET /api/drivers` - List all drivers
- `POST /api/drivers` - Create new driver
- `GET /api/drivers/{id}` - Get driver details
- `PUT /api/drivers/{id}` - Update driver
- `DELETE /api/drivers/{id}` - Delete driver

### Routes
- `GET /api/routes` - List all routes
- `POST /api/routes` - Create new route
- `GET /api/routes/{id}` - Get route details
- `POST /api/routes/{id}/optimize` - Optimize route order
- `POST /api/routes/{id}/orders` - Add orders to route
- `DELETE /api/routes/{id}` - Delete route

### Locations
- `GET /api/locations/depots` - List depots
- `POST /api/locations/depots` - Create depot
- `GET /api/locations/parking` - List parking locations
- `POST /api/locations/parking` - Create parking location

## Development

### Project Structure

```
/
├── backend/
│   ├── main.py              # FastAPI app entry point
│   ├── models.py            # Pydantic models
│   ├── database.py          # SQLAlchemy models and database setup
│   ├── api/                 # API endpoints
│   │   ├── orders.py
│   │   ├── drivers.py
│   │   ├── locations.py
│   │   └── routes.py
│   └── services/           # Business logic
│       ├── order_parser.py
│       ├── order_validator.py
│       ├── route_calculator.py
│       ├── route_optimizer.py
│       ├── ai_agents.py
│       └── geocoding.py
├── frontend/
│   └── planner/            # Planner interface
│       ├── index.html
│       ├── app.js
│       └── styles.css
├── uploads/                 # Temporary file storage
└── requirements.txt
```

## Notes

- The system uses SQLite for easy local deployment
- **Routing**: Uses OSRM for accurate road-based routing (optional, falls back to Haversine if unavailable)
- OCR requires Tesseract to be installed on the system
- Route optimization uses OR-Tools (open-source) with OSRM distance matrix, falls back to simple nearest-neighbor algorithm
- Geocoding uses Nominatim (free, but rate-limited)
- For production use, consider:
  - Using PostgreSQL instead of SQLite
  - Setting up OSRM for accurate routing (see [OSRM_SETUP.md](OSRM_SETUP.md))
  - Setting up proper authentication
  - Adding rate limiting
  - Using a cloud OCR service for better accuracy
  - Implementing WebSocket for real-time updates

## License

This project is created for the HHN City Hackathon.
