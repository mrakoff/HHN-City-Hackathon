# Quick Start Guide

## Installation

1. **Activate the virtual environment:**
   ```bash
   source .venv/bin/activate
   ```

2. **Install Tesseract OCR** (required for document parsing):
   ```bash
   # macOS
   brew install tesseract

   # Ubuntu/Debian
   sudo apt-get install tesseract-ocr

   # Windows
   # Download from: https://github.com/UB-Mannheim/tesseract/wiki
   ```

3. **Optional: Install OR-Tools** (for advanced route optimization):
   ```bash
   # Note: OR-Tools supports Python 3.8-3.12
   # If using Python 3.14, the system will use a fallback algorithm
   pip install ortools
   ```

4. **Optional: Set OpenAI API key** (for AI-powered order parsing):
   ```bash
   export OPENAI_API_KEY=your_api_key_here
   ```

## Running the Application

1. **Start the server:**
   ```bash
   source .venv/bin/activate
   uvicorn backend.main:app --reload
   ```

2. **Open your browser:**
   ```
   http://localhost:8000
   ```

## First Steps

1. **Add a Depot:**
   - Go to "Locations" tab
   - Click "Add Depot"
   - Enter your warehouse/distribution center address

2. **Add Drivers:**
   - Go to "Drivers" tab
   - Click "Add Driver"
   - Enter driver information

3. **Add Orders:**
   - Go to "Orders" tab
   - Click "Add Order" for manual entry
   - Or click "Upload Document" to scan orders from email/fax/mail

4. **Create Routes:**
   - Go to "Routes" tab
   - Create a route and assign orders
   - Click "Optimize" to automatically reorder stops

## Notes

- **Python 3.14 Compatibility:** Some packages may have limited support. The system includes fallbacks for missing optional dependencies.
- **OR-Tools:** If not installed, the system uses a simple nearest-neighbor optimization algorithm.
- **OCR:** Requires Tesseract to be installed on your system.
- **Geocoding:** Uses free Nominatim service (rate-limited, but sufficient for development).

## Troubleshooting

**Issue: OR-Tools not installing**
- OR-Tools may not support Python 3.14. The system will automatically use a fallback algorithm.

**Issue: OCR not working**
- Make sure Tesseract is installed: `tesseract --version`
- Check that pytesseract can find it: `python -c "import pytesseract; print(pytesseract.get_tesseract_version())"`

**Issue: Database errors**
- Delete `route_planning.db` and restart the server to recreate the database.
