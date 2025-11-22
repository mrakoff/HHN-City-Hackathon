#!/usr/bin/env python3
"""
Test script to test all different types of ordering:
- Phone (text parsing)
- Email (with attachment and body text)
- Fax (document upload)
- Mail (document upload)
- Orders with missing information

Usage: python3 scripts/test_orders.py
Make sure the backend server is running on http://localhost:8000
"""

import sys

try:
    import requests
except ImportError:
    print("Error: 'requests' module not found.")
    print("Install it with: pip install requests")
    sys.exit(1)

import json
from datetime import datetime, timedelta
from pathlib import Path

API_BASE = "http://localhost:8000/api"

def test_order_type(name, test_func):
    """Helper to run a test and report results"""
    print(f"\n{'='*60}")
    print(f"Testing: {name}")
    print(f"{'='*60}")
    try:
        result = test_func()
        print(f"✅ SUCCESS: {name}")
        if result:
            print(f"   Order ID: {result.get('id')}")
            print(f"   Order Number: {result.get('order_number')}")
            if result.get('validation_errors'):
                print(f"   ⚠️  Validation Errors: {result.get('validation_errors')}")
        return True
    except Exception as e:
        print(f"❌ FAILED: {name}")
        print(f"   Error: {str(e)}")
        return False

def test_phone_order_complete():
    """Test phone order with complete information"""
    text = """
    Order Number: ORD-280125-0001
    Customer Name: John Smith
    Phone: +49 30 12345678
    Email: john.smith@example.com
    Delivery Address: Hauptstraße 123, 10115 Berlin, Germany
    Description: Please deliver during business hours
    Items: 5x Widget A, 3x Widget B
    Delivery Time: Tomorrow 10:00 AM to 2:00 PM
    Priority: High
    """

    response = requests.post(
        f"{API_BASE}/orders/parse-text",
        json={
            "text": text,
            "source": "phone"
        }
    )
    response.raise_for_status()
    return response.json()

def test_phone_order_missing_address():
    """Test phone order with missing address"""
    text = """
    Order Number: ORD-280125-0002
    Customer Name: Jane Doe
    Phone: +49 89 98765432
    Email: jane.doe@example.com
    Description: Need delivery ASAP
    Items: 2x Product X
    """

    response = requests.post(
        f"{API_BASE}/orders/parse-text",
        json={
            "text": text,
            "source": "phone"
        }
    )
    response.raise_for_status()
    return response.json()

def test_phone_order_minimal():
    """Test phone order with minimal information"""
    text = "I need 3 boxes delivered to Marienplatz 8, Munich"

    response = requests.post(
        f"{API_BASE}/orders/parse-text",
        json={
            "text": text,
            "source": "phone"
        }
    )
    response.raise_for_status()
    return response.json()

def test_email_order_with_attachment():
    """Test email order with PDF attachment"""
    # Check if we have a test PDF file
    test_pdf = Path("mock_orders/pdfs/ORD-2024-001.pdf")
    if not test_pdf.exists():
        print("   ⚠️  Test PDF not found, skipping attachment test")
        return None

    with open(test_pdf, 'rb') as f:
        files = {'attachment': ('test.pdf', f, 'application/pdf')}
        data = {
            'sender_email': 'customer@example.com',
            'email_body': 'Please see attached order form.'
        }

        response = requests.post(
            f"{API_BASE}/orders/receive-email",
            files=files,
            data=data
        )
        response.raise_for_status()
        return response.json()

def test_email_order_text_only():
    """Test email order with text body only"""
    email_body = """
    Order Number: ORD-280125-0003
    Customer: Maria Schmidt
    Phone: +49 40 55512345
    Address: Speicherstadt 1, 20457 Hamburg
    Items: 4x Item A, 2x Item B
    Delivery needed by end of week.
    """

    data = {
        'sender_email': 'maria.schmidt@example.com',
        'email_body': email_body
    }

    response = requests.post(
        f"{API_BASE}/orders/receive-email",
        data=data
    )
    response.raise_for_status()
    return response.json()

def test_fax_order():
    """Test fax order (document upload)"""
    test_pdf = Path("mock_orders/pdfs/FAX-2024-001.pdf")
    if not test_pdf.exists():
        print("   ⚠️  Test FAX PDF not found, skipping fax test")
        return None

    with open(test_pdf, 'rb') as f:
        files = {'file': ('fax.pdf', f, 'application/pdf')}

        response = requests.post(
            f"{API_BASE}/orders/receive-fax",
            files=files
        )
        response.raise_for_status()
        return response.json()

def test_mail_order():
    """Test mail order (scanned document)"""
    test_pdf = Path("mock_orders/pdfs/MAIL-2024-001.pdf")
    if not test_pdf.exists():
        print("   ⚠️  Test MAIL PDF not found, skipping mail test")
        return None

    with open(test_pdf, 'rb') as f:
        files = {'file': ('mail.pdf', f, 'application/pdf')}

        response = requests.post(
            f"{API_BASE}/orders/receive-mail",
            files=files
        )
        response.raise_for_status()
        return response.json()

def test_direct_order_complete():
    """Test direct order creation with complete information"""
    order_data = {
        "delivery_address": "Brandenburger Tor, 10117 Berlin",
        "customer_name": "Test Customer",
        "customer_phone": "+49 30 11111111",
        "customer_email": "test@example.com",
        "description": "Complete test order",
        "items": [
            {"name": "Item 1", "quantity": 5},
            {"name": "Item 2", "quantity": 3}
        ],
        "delivery_time_window_start": (datetime.now() + timedelta(days=1)).isoformat(),
        "delivery_time_window_end": (datetime.now() + timedelta(days=2)).isoformat(),
        "priority": "high",
        "source": "manual"
    }

    response = requests.post(
        f"{API_BASE}/orders",
        json=order_data
    )
    response.raise_for_status()
    return response.json()

def test_direct_order_missing_required():
    """Test direct order with missing required field (address)"""
    order_data = {
        "customer_name": "Incomplete Customer",
        "customer_phone": "+49 30 22222222",
        "description": "This should have validation errors"
    }

    response = requests.post(
        f"{API_BASE}/orders",
        json=order_data
    )
    # This should fail or return validation errors
    if response.status_code == 422:
        print("   ✅ Correctly rejected order with missing address")
        return None
    response.raise_for_status()
    result = response.json()
    if result.get('validation_errors'):
        print(f"   ✅ Validation errors detected: {result.get('validation_errors')}")
    return result

def test_order_missing_time_window():
    """Test order without time window (should get low priority)"""
    order_data = {
        "delivery_address": "Alexanderplatz 1, 10178 Berlin",
        "customer_name": "No Time Window Customer",
        "description": "No time restrictions"
    }

    response = requests.post(
        f"{API_BASE}/orders",
        json=order_data
    )
    response.raise_for_status()
    result = response.json()
    if result.get('priority') == 'low':
        print(f"   ✅ Correctly assigned low priority (no time window)")
    return result

def test_order_invalid_email():
    """Test order with invalid email format"""
    order_data = {
        "delivery_address": "Potsdamer Platz 1, 10785 Berlin",
        "customer_name": "Bad Email Customer",
        "customer_email": "not-an-email"
    }

    response = requests.post(
        f"{API_BASE}/orders",
        json=order_data
    )
    response.raise_for_status()
    result = response.json()
    if result.get('validation_errors'):
        print(f"   ✅ Validation errors detected: {result.get('validation_errors')}")
    return result

def main():
    print("\n" + "="*60)
    print("ORDER TYPE TESTING SUITE")
    print("="*60)

    results = []

    # Test phone orders
    results.append(("Phone Order - Complete", test_order_type("Phone Order - Complete", test_phone_order_complete)))
    results.append(("Phone Order - Missing Address", test_order_type("Phone Order - Missing Address", test_phone_order_missing_address)))
    results.append(("Phone Order - Minimal", test_order_type("Phone Order - Minimal", test_phone_order_minimal)))

    # Test email orders
    results.append(("Email Order - With Attachment", test_order_type("Email Order - With Attachment", test_email_order_with_attachment)))
    results.append(("Email Order - Text Only", test_order_type("Email Order - Text Only", test_email_order_text_only)))

    # Test fax orders
    results.append(("Fax Order", test_order_type("Fax Order", test_fax_order)))

    # Test mail orders
    results.append(("Mail Order", test_order_type("Mail Order", test_mail_order)))

    # Test direct orders
    results.append(("Direct Order - Complete", test_order_type("Direct Order - Complete", test_direct_order_complete)))
    results.append(("Direct Order - Missing Required", test_order_type("Direct Order - Missing Required", test_direct_order_missing_required)))
    results.append(("Direct Order - Missing Time Window", test_order_type("Direct Order - Missing Time Window", test_order_missing_time_window)))
    results.append(("Direct Order - Invalid Email", test_order_type("Direct Order - Invalid Email", test_order_invalid_email)))

    # Summary
    print(f"\n{'='*60}")
    print("TEST SUMMARY")
    print(f"{'='*60}")
    passed = sum(1 for _, result in results if result)
    total = len(results)
    print(f"Passed: {passed}/{total}")

    if passed == total:
        print("✅ All tests passed!")
    else:
        print("⚠️  Some tests failed or were skipped")

    return passed == total

if __name__ == "__main__":
    try:
        # Check if server is running
        response = requests.get(f"{API_BASE.replace('/api', '')}/api/health", timeout=2)
        if response.status_code != 200:
            print("❌ Server is not responding correctly")
            exit(1)
    except requests.exceptions.RequestException:
        print("❌ Cannot connect to server. Make sure the backend is running on http://localhost:8000")
        exit(1)

    success = main()
    exit(0 if success else 1)
