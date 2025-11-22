# Testing Guide

This document describes how to test all order types and verify the system is working correctly.

## Prerequisites

1. Make sure the backend server is running:
   ```bash
   cd backend
   uvicorn main:app --reload
   ```

2. Install dependencies if needed:
   ```bash
   pip install -r requirements.txt
   ```

## Adding 5 Drivers

To add 5 test drivers to the database:

```bash
python3 scripts/add_drivers.py
```

This will add:
- Michael Schneider (available)
- Anna Weber (available)
- Thomas Fischer (on_route)
- Sarah Müller (available)
- David Klein (offline)

All drivers are editable through the frontend interface.

## Testing Order Types

Run the comprehensive test suite:

```bash
python3 scripts/test_orders.py
```

This will test:

### 1. Phone Orders
- **Complete order**: Full information including address, customer details, items, time window
- **Missing address**: Order without delivery address (should show validation errors)
- **Minimal order**: Very basic order with just address

### 2. Email Orders
- **With attachment**: Email with PDF attachment
- **Text only**: Email with order information in body text

### 3. Fax Orders
- Document upload via fax endpoint

### 4. Mail Orders
- Scanned physical mail document upload

### 5. Direct Orders
- **Complete**: Full order created via API
- **Missing required fields**: Order without address (should be rejected or show errors)
- **Missing time window**: Order without time restrictions (should get low priority)
- **Invalid email**: Order with malformed email (should show validation errors)

## Testing Missing Information

The system handles missing information as follows:

1. **Missing delivery address**:
   - Order is created but marked with validation errors
   - Shows as "UNFINISHED" in the frontend
   - Can be edited to add the missing address

2. **Missing customer information**:
   - Order is still created (customer info is optional)
   - Can be added later through editing

3. **Missing time window**:
   - Order gets "low" priority automatically
   - Can be updated later

4. **Invalid email format**:
   - Validation error is added
   - Order is still created but marked as unfinished

## Frontend Testing

1. Open the frontend in your browser: `http://localhost:8000`

2. Test order creation:
   - Click "Add Order" to create a manual order
   - Click "Upload Document" to test document parsing
   - Click "📞 Simulate Phone Call" to test phone order transcription

3. Test driver management:
   - View all drivers in the "Drivers" tab
   - Click "Edit" on any driver to modify their information
   - Drivers can be edited: name, phone, email, and status

4. Test order editing:
   - Click "Edit" on any order to modify it
   - Fix validation errors by adding missing information
   - Update priority, status, and other fields

## Expected Results

- All order types should be parsed correctly
- Orders with missing critical information (like address) should show validation errors
- Orders should be visible in the "Unfinished Orders" view if they have errors
- All 5 drivers should be visible and editable
- Priority should be auto-calculated based on delivery time window

## Troubleshooting

If tests fail:
1. Check that the backend server is running
2. Verify database file exists: `route_planning.db`
3. Check server logs for errors
4. Ensure all dependencies are installed
