#!/usr/bin/env python3
"""
Send mock orders via email, fax, and mail channels to test the order reception endpoints.
"""

import os
import sys
import requests
from pathlib import Path
from typing import Optional

# Add parent directory to path to import backend modules if needed
script_dir = Path(__file__).parent
parent_dir = script_dir.parent
sys.path.insert(0, str(parent_dir))


BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")


def send_email_order(email_body: Optional[str] = None, attachment_path: Optional[Path] = None,
                     sender_email: Optional[str] = None) -> dict:
    """Send an order via the email channel"""
    url = f"{BASE_URL}/api/orders/receive-email"

    data = {}
    files = {}

    if sender_email:
        data['sender_email'] = sender_email

    if email_body:
        data['email_body'] = email_body

    if attachment_path and attachment_path.exists():
        # Determine content type based on file extension
        ext = attachment_path.suffix.lower()
        if ext == '.pdf':
            content_type = 'application/pdf'
        elif ext in ['.png', '.jpg', '.jpeg']:
            content_type = 'image/png' if ext == '.png' else 'image/jpeg'
        else:
            content_type = 'application/octet-stream'

        with open(attachment_path, 'rb') as f:
            files['attachment'] = (attachment_path.name, f, content_type)
            if not email_body:
                data['email_body'] = ""  # Empty string if only attachment
            response = requests.post(url, data=data, files=files)
    else:
        if not email_body:
            raise ValueError("Either email_body or attachment_path must be provided")
        response = requests.post(url, data=data)

    response.raise_for_status()
    return response.json()


def send_fax_order(document_path: Path) -> dict:
    """Send an order via the fax channel"""
    url = f"{BASE_URL}/api/orders/receive-fax"

    if not document_path.exists():
        raise FileNotFoundError(f"Document not found: {document_path}")

    # Determine content type based on file extension
    ext = document_path.suffix.lower()
    if ext == '.pdf':
        content_type = 'application/pdf'
    elif ext in ['.png', '.jpg', '.jpeg']:
        content_type = 'image/png' if ext == '.png' else 'image/jpeg'
    else:
        content_type = 'application/octet-stream'

    with open(document_path, 'rb') as f:
        files = {'file': (document_path.name, f, content_type)}
        response = requests.post(url, files=files)

    response.raise_for_status()
    return response.json()


def send_mail_order(document_path: Path) -> dict:
    """Send an order via the mail channel (scanned physical mail)"""
    url = f"{BASE_URL}/api/orders/receive-mail"

    if not document_path.exists():
        raise FileNotFoundError(f"Document not found: {document_path}")

    # Determine content type based on file extension
    ext = document_path.suffix.lower()
    content_type = 'application/pdf' if ext == '.pdf' else 'image/png'

    with open(document_path, 'rb') as f:
        files = {'file': (document_path.name, f, content_type)}
        response = requests.post(url, files=files)

    response.raise_for_status()
    return response.json()


def main():
    """Send mock orders via all three channels"""
    # Find mock orders directory
    script_dir = Path(__file__).parent
    mock_orders_dir = script_dir / "mock_orders"

    if not mock_orders_dir.exists():
        print(f"Error: Mock orders directory not found: {mock_orders_dir}")
        print("Please run generate_mock_orders.py first to create mock orders.")
        sys.exit(1)

    pdf_dir = mock_orders_dir / "pdfs"
    image_dir = mock_orders_dir / "images"
    text_dir = mock_orders_dir / "text"

    print(f"Connecting to API at: {BASE_URL}")
    print("\nSending mock orders...\n")

    # Test health endpoint first
    try:
        response = requests.get(f"{BASE_URL}/api/health", timeout=5)
        if response.status_code != 200:
            print(f"Warning: API health check returned status {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"Error: Could not connect to API at {BASE_URL}")
        print(f"Make sure the server is running: uvicorn backend.main:app --reload")
        sys.exit(1)

    results = {
        "email": [],
        "fax": [],
        "mail": []
    }

    # Send orders via EMAIL channel
    print("=" * 60)
    print("EMAIL CHANNEL")
    print("=" * 60)

    # Email 1: With PDF attachment (well-formatted)
    if (pdf_dir / "ORD-2024-001.pdf").exists():
        try:
            result = send_email_order(
                attachment_path=pdf_dir / "ORD-2024-001.pdf",
                sender_email="thomas.mueller@example.de"
            )
            results["email"].append({"file": "ORD-2024-001.pdf", "status": "success", "order_id": result.get("id")})
            print(f"✓ Sent email with attachment: ORD-2024-001.pdf -> Order ID: {result.get('id')}")
        except requests.exceptions.HTTPError as e:
            error_detail = str(e)
            try:
                error_json = e.response.json()
                error_detail = error_json.get('detail', error_detail)
            except:
                pass
            results["email"].append({"file": "ORD-2024-001.pdf", "status": "error", "error": error_detail})
            print(f"✗ Failed to send email with attachment: {error_detail}")
        except Exception as e:
            results["email"].append({"file": "ORD-2024-001.pdf", "status": "error", "error": str(e)})
            print(f"✗ Failed to send email with attachment: {e}")

    # Email 2: With text body only
    if (text_dir / "ORD-2024-002.txt").exists():
        try:
            with open(text_dir / "ORD-2024-002.txt", 'r') as f:
                email_body = f.read()
            result = send_email_order(
                email_body=email_body,
                sender_email="maria.schmidt@example.de"
            )
            results["email"].append({"file": "ORD-2024-002.txt", "status": "success", "order_id": result.get("id")})
            print(f"✓ Sent email with text body: ORD-2024-002.txt -> Order ID: {result.get('id')}")
        except requests.exceptions.HTTPError as e:
            error_detail = str(e)
            try:
                error_json = e.response.json()
                error_detail = error_json.get('detail', error_detail)
            except:
                pass
            results["email"].append({"file": "ORD-2024-002.txt", "status": "error", "error": error_detail})
            print(f"✗ Failed to send email with text body: {error_detail}")
        except Exception as e:
            results["email"].append({"file": "ORD-2024-002.txt", "status": "error", "error": str(e)})
            print(f"✗ Failed to send email with text body: {e}")

    # Email 3: With image attachment (poorly formatted)
    if (image_dir / "ORD-2024-003.png").exists():
        try:
            result = send_email_order(
                attachment_path=image_dir / "ORD-2024-003.png",
                sender_email="robert.fischer@example.de"
            )
            results["email"].append({"file": "ORD-2024-003.png", "status": "success", "order_id": result.get("id")})
            print(f"✓ Sent email with image attachment: ORD-2024-003.png -> Order ID: {result.get('id')}")
        except requests.exceptions.HTTPError as e:
            error_detail = str(e)
            try:
                error_json = e.response.json()
                error_detail = error_json.get('detail', error_detail)
            except:
                pass
            results["email"].append({"file": "ORD-2024-003.png", "status": "error", "error": error_detail})
            print(f"✗ Failed to send email with image attachment: {error_detail}")
        except Exception as e:
            results["email"].append({"file": "ORD-2024-003.png", "status": "error", "error": str(e)})
            print(f"✗ Failed to send email with image attachment: {e}")

    # Send orders via FAX channel
    print("\n" + "=" * 60)
    print("FAX CHANNEL")
    print("=" * 60)

    # Fax 1: Well-formatted PDF
    if (pdf_dir / "FAX-2024-001.pdf").exists():
        try:
            result = send_fax_order(pdf_dir / "FAX-2024-001.pdf")
            results["fax"].append({"file": "FAX-2024-001.pdf", "status": "success", "order_id": result.get("id")})
            print(f"✓ Sent fax: FAX-2024-001.pdf -> Order ID: {result.get('id')}")
        except requests.exceptions.HTTPError as e:
            error_detail = str(e)
            try:
                error_json = e.response.json()
                error_detail = error_json.get('detail', error_detail)
            except:
                pass
            results["fax"].append({"file": "FAX-2024-001.pdf", "status": "error", "error": error_detail})
            print(f"✗ Failed to send fax: {error_detail}")
        except Exception as e:
            results["fax"].append({"file": "FAX-2024-001.pdf", "status": "error", "error": str(e)})
            print(f"✗ Failed to send fax: {e}")

    # Fax 2: Image format
    if (image_dir / "ORD-2024-001.png").exists():
        try:
            result = send_fax_order(image_dir / "ORD-2024-001.png")
            results["fax"].append({"file": "ORD-2024-001.png", "status": "success", "order_id": result.get("id")})
            print(f"✓ Sent fax (image): ORD-2024-001.png -> Order ID: {result.get('id')}")
        except requests.exceptions.HTTPError as e:
            error_detail = str(e)
            try:
                error_json = e.response.json()
                error_detail = error_json.get('detail', error_detail)
            except:
                pass
            results["fax"].append({"file": "ORD-2024-001.png", "status": "error", "error": error_detail})
            print(f"✗ Failed to send fax (image): {error_detail}")
        except Exception as e:
            results["fax"].append({"file": "ORD-2024-001.png", "status": "error", "error": str(e)})
            print(f"✗ Failed to send fax (image): {e}")

    # Send orders via MAIL channel
    print("\n" + "=" * 60)
    print("MAIL CHANNEL")
    print("=" * 60)

    # Mail 1: Scanned document (PDF)
    if (pdf_dir / "MAIL-2024-001.pdf").exists():
        try:
            result = send_mail_order(pdf_dir / "MAIL-2024-001.pdf")
            results["mail"].append({"file": "MAIL-2024-001.pdf", "status": "success", "order_id": result.get("id")})
            print(f"✓ Sent scanned mail: MAIL-2024-001.pdf -> Order ID: {result.get('id')}")
        except requests.exceptions.HTTPError as e:
            error_detail = str(e)
            try:
                error_json = e.response.json()
                error_detail = error_json.get('detail', error_detail)
            except:
                pass
            results["mail"].append({"file": "MAIL-2024-001.pdf", "status": "error", "error": error_detail})
            print(f"✗ Failed to send scanned mail: {error_detail}")
        except Exception as e:
            results["mail"].append({"file": "MAIL-2024-001.pdf", "status": "error", "error": str(e)})
            print(f"✗ Failed to send scanned mail: {e}")

    # Mail 2: Scanned document (image - poorly formatted)
    if (image_dir / "MAIL-2024-001.png").exists():
        try:
            result = send_mail_order(image_dir / "MAIL-2024-001.png")
            results["mail"].append({"file": "MAIL-2024-001.png", "status": "success", "order_id": result.get("id")})
            print(f"✓ Sent scanned mail (image): MAIL-2024-001.png -> Order ID: {result.get('id')}")
        except requests.exceptions.HTTPError as e:
            error_detail = str(e)
            try:
                error_json = e.response.json()
                error_detail = error_json.get('detail', error_detail)
            except:
                pass
            results["mail"].append({"file": "MAIL-2024-001.png", "status": "error", "error": error_detail})
            print(f"✗ Failed to send scanned mail (image): {error_detail}")
        except Exception as e:
            results["mail"].append({"file": "MAIL-2024-001.png", "status": "error", "error": str(e)})
            print(f"✗ Failed to send scanned mail (image): {e}")

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    total_sent = sum(len([r for r in results[channel] if r["status"] == "success"]) for channel in results)
    total_failed = sum(len([r for r in results[channel] if r["status"] == "error"]) for channel in results)

    for channel in ["email", "fax", "mail"]:
        channel_results = results[channel]
        success_count = len([r for r in channel_results if r["status"] == "success"])
        error_count = len([r for r in channel_results if r["status"] == "error"])

        print(f"\n{channel.upper()}:")
        print(f"  Success: {success_count}")
        print(f"  Errors: {error_count}")

        if error_count > 0:
            print("  Failed files:")
            for r in channel_results:
                if r["status"] == "error":
                    print(f"    - {r['file']}: {r.get('error', 'Unknown error')}")

    print(f"\nTotal: {total_sent} sent successfully, {total_failed} failed")

    if total_failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
