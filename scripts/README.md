# Mock Order Testing Scripts

This directory contains scripts for testing the order reception system via email, fax, and mail channels.

## Scripts

### `generate_mock_orders.py`
Generates sample order documents in multiple formats:
- PDF files (requires `reportlab`)
- PNG images (requires `Pillow`)
- Text files (for email body content)

**Usage:**
```bash
python3 scripts/generate_mock_orders.py
```

This creates a `mock_orders` directory with subdirectories:
- `mock_orders/pdfs/` - PDF order documents
- `mock_orders/images/` - Image order documents
- `mock_orders/text/` - Text order documents

### `send_mock_orders.py`
Sends mock orders via all three channels (email, fax, mail) to test the API endpoints.

**Usage:**
```bash
# Make sure the API server is running
uvicorn backend.main:app --reload

# In another terminal, send mock orders
python3 scripts/send_mock_orders.py
```

**Environment Variables:**
- `API_BASE_URL` - Base URL for the API (default: `http://localhost:8000`)

**Example:**
```bash
API_BASE_URL=http://localhost:8000 python3 scripts/send_mock_orders.py
```

## Testing Flow

1. **Generate mock orders:**
   ```bash
   python3 scripts/generate_mock_orders.py
   ```

2. **Start the API server:**
   ```bash
   uvicorn backend.main:app --reload
   ```

3. **Send mock orders via all channels:**
   ```bash
   python3 scripts/send_mock_orders.py
   ```

4. **Verify orders in database:**
   - Check the `/api/orders` endpoint
   - Filter by source: `/api/orders?source=email`, `/api/orders?source=fax`, `/api/orders?source=mail`

## API Endpoints

The scripts test these endpoints:

- `POST /api/orders/receive-email` - Receive order via email
  - Accepts: `sender_email`, `email_body`, `attachment` (optional)

- `POST /api/orders/receive-fax` - Receive order via fax
  - Accepts: `file` (PDF or image)

- `POST /api/orders/receive-mail` - Receive scanned physical mail
  - Accepts: `file` (PDF or image)

## Dependencies

Install required dependencies:
```bash
pip install -r requirements.txt
```

For PDF generation: `reportlab>=4.0.0`
For image generation: `Pillow>=10.2.0` (already in requirements.txt)

## Mock Order Data

The scripts generate 5 sample orders with different characteristics:
- Well-formatted orders
- Poorly formatted orders (to test parsing robustness)
- Orders with missing information
- Various priority levels
- Different delivery time windows
