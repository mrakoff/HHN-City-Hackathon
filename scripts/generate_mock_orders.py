#!/usr/bin/env python3
"""
Generate mock order documents for testing email, fax, and mail channels.
Creates sample PDF and image files with order information.
"""

import os
from datetime import datetime, timedelta
from typing import Dict, List
from pathlib import Path

try:
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    from reportlab.lib.units import inch
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False
    print("Warning: reportlab not available. PDF generation will be skipped.")

try:
    from PIL import Image, ImageDraw, ImageFont
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    print("Warning: Pillow not available. Image generation will be skipped.")


# Sample order data with German locations
# Order numbers are generated in format ORD-ddmmyy-XXXX
MOCK_ORDERS = [
    {
        "order_number": None,  # Will be generated as ORD-ddmmyy-0001
        "customer_name": "Thomas Müller",
        "customer_email": "thomas.mueller@example.de",
        "customer_phone": "+49 30 12345678",
        "delivery_address": "Hauptstraße 123, 10115 Berlin",
        "description": "Standard delivery for office supplies. Please deliver during business hours.",
        "items": [
            {"name": "Widget A", "quantity": 5},
            {"name": "Widget B", "quantity": 3},
            {"name": "Widget C", "quantity": 2}
        ],
        "priority": None,  # Will be auto-calculated: normal (1-2 days away)
        "delivery_time_window_start": datetime.now() + timedelta(days=1),
        "delivery_time_window_end": datetime.now() + timedelta(days=2),
        "format": "well_formatted"
    },
    {
        "order_number": None,  # Will be generated as ORD-ddmmyy-0002
        "customer_name": "Maria Schmidt",
        "customer_email": "maria.schmidt@example.de",
        "customer_phone": "+49 89 98765432",
        "delivery_address": "Marienplatz 8, 80331 München",
        "description": "Urgent delivery needed for event tomorrow. Please handle with care.",
        "items": [
            {"name": "Product X", "quantity": 10},
            {"name": "Product Y", "quantity": 1}
        ],
        "priority": None,  # Will be auto-calculated: urgent (< 24 hours)
        "delivery_time_window_start": datetime.now() + timedelta(hours=12),
        "delivery_time_window_end": datetime.now() + timedelta(days=1),
        "format": "well_formatted"
    },
    {
        "order_number": None,  # Will be generated as ORD-ddmmyy-0003
        "customer_name": "Robert Fischer",
        "customer_email": None,
        "customer_phone": "+49 40 55512345",
        "delivery_address": "Speicherstadt 1, 20457 Hamburg",
        "description": "No specific delivery time required. Standard shipping.",
        "items": [
            {"name": "Item 1", "quantity": 4},
            {"name": "Item 2", "quantity": 6},
            {"name": "Special Item", "quantity": 1}
        ],
        "priority": None,  # Will be auto-calculated: low (no time window)
        "delivery_time_window_start": None,
        "delivery_time_window_end": None,
        "format": "poorly_formatted"
    },
    {
        "order_number": None,  # Will be generated as ORD-ddmmyy-0004 (FAX source)
        "customer_name": "Lisa Weber",
        "customer_email": "lisa.weber@example.de",
        "customer_phone": "+49 69 23456789",
        "delivery_address": "Zeil 45, 60313 Frankfurt am Main",
        "description": "Bulk order for warehouse. Delivery window: 3-4 days from now.",
        "items": [
            {"name": "Component A", "quantity": 8}
        ],
        "priority": None,  # Will be auto-calculated: normal (> 3 days away)
        "delivery_time_window_start": datetime.now() + timedelta(days=3),
        "delivery_time_window_end": datetime.now() + timedelta(days=4),
        "format": "well_formatted"
    },
    {
        "order_number": None,  # Will be generated as ORD-ddmmyy-0005 (MAIL source)
        "customer_name": "David Schneider",
        "customer_email": "d.schneider@example.de",
        "customer_phone": "+49 221 34567890",
        "delivery_address": "Hohe Straße 78, 50667 Köln",
        "description": "Regular order, no rush. Deliver when convenient.",
        "items": [
            {"name": "Box Set A", "quantity": 2},
            {"name": "Box Set B", "quantity": 2}
        ],
        "priority": None,  # Will be auto-calculated: low (no time window)
        "delivery_time_window_start": None,
        "delivery_time_window_end": None,
        "format": "poorly_formatted"
    }
]


def create_pdf_order(order: Dict, output_dir: Path, format_type: str = "well_formatted"):
    """Create a PDF order document"""
    if not REPORTLAB_AVAILABLE:
        return None

    filename = f"{order['order_number']}.pdf"
    filepath = output_dir / filename

    c = canvas.Canvas(str(filepath), pagesize=letter)
    width, height = letter

    # Title
    c.setFont("Helvetica-Bold", 16)
    c.drawString(72, height - 72, "ORDER FORM")

    y_pos = height - 100

    if format_type == "well_formatted":
        # Well-formatted order
        c.setFont("Helvetica", 12)
        c.drawString(72, y_pos, f"Order Number: {order['order_number']}")
        y_pos -= 25

        c.drawString(72, y_pos, f"Customer Name: {order['customer_name']}")
        y_pos -= 25

        if order.get('customer_email'):
            c.drawString(72, y_pos, f"Email: {order['customer_email']}")
            y_pos -= 25

        if order.get('customer_phone'):
            c.drawString(72, y_pos, f"Phone: {order['customer_phone']}")
            y_pos -= 25

        c.drawString(72, y_pos, f"Delivery Address: {order['delivery_address']}")
        y_pos -= 30

        if order.get('description'):
            c.drawString(72, y_pos, f"Description: {order['description']}")
            y_pos -= 30

        c.drawString(72, y_pos, "Items:")
        y_pos -= 20

        for item in order.get('items', []):
            c.drawString(100, y_pos, f"  {item['quantity']}x {item['name']}")
            y_pos -= 20

        y_pos -= 10
        priority = order.get('priority') or 'normal'
        c.drawString(72, y_pos, f"Priority: {priority.upper()}")

        if order.get('delivery_time_window_start'):
            y_pos -= 20
            start_str = order['delivery_time_window_start'].strftime("%Y-%m-%d %H:%M")
            end_str = order['delivery_time_window_end'].strftime("%Y-%m-%d %H:%M")
            c.drawString(72, y_pos, f"Delivery Window: {start_str} to {end_str}")

    else:
        # Poorly formatted order
        c.setFont("Helvetica", 11)
        text = f"""
Order #{order['order_number']}
{order['customer_name']}
Phone: {order.get('customer_phone', 'N/A')}
{order['delivery_address']}

Items:
"""
        for item in order.get('items', []):
            text += f"  {item['quantity']} {item['name']}\n"

        priority = order.get('priority') or 'normal'
        text += f"\nPriority: {priority}"

        # Draw as a block of text (less structured)
        text_lines = text.strip().split('\n')
        for line in text_lines:
            c.drawString(72, y_pos, line)
            y_pos -= 18

    c.save()
    return filepath


def create_image_order(order: Dict, output_dir: Path, format_type: str = "well_formatted"):
    """Create an image order document (simulated scan)"""
    if not PIL_AVAILABLE:
        return None

    # Create a white background image
    img_width, img_height = 800, 1000
    img = Image.new('RGB', (img_width, img_height), color='white')
    draw = ImageDraw.Draw(img)

    # Try to use a default font, fallback to basic if not available
    try:
        font_large = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 24)
        font_medium = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 18)
        font_small = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 14)
    except:
        try:
            font_large = ImageFont.truetype("arial.ttf", 24)
            font_medium = ImageFont.truetype("arial.ttf", 18)
            font_small = ImageFont.truetype("arial.ttf", 14)
        except:
            font_large = ImageFont.load_default()
            font_medium = ImageFont.load_default()
            font_small = ImageFont.load_default()

    y_pos = 50

    if format_type == "well_formatted":
        # Well-formatted order
        draw.text((50, y_pos), "ORDER FORM", fill='black', font=font_large)
        y_pos += 50

        draw.text((50, y_pos), f"Order Number: {order['order_number']}", fill='black', font=font_medium)
        y_pos += 35

        draw.text((50, y_pos), f"Customer Name: {order['customer_name']}", fill='black', font=font_small)
        y_pos += 30

        if order.get('customer_email'):
            draw.text((50, y_pos), f"Email: {order['customer_email']}", fill='black', font=font_small)
            y_pos += 30

        if order.get('customer_phone'):
            draw.text((50, y_pos), f"Phone: {order['customer_phone']}", fill='black', font=font_small)
            y_pos += 30

        draw.text((50, y_pos), f"Delivery Address: {order['delivery_address']}", fill='black', font=font_small)
        y_pos += 40

        if order.get('description'):
            draw.text((50, y_pos), f"Description: {order['description']}", fill='black', font=font_small)
            y_pos += 40

        draw.text((50, y_pos), "Items:", fill='black', font=font_medium)
        y_pos += 35

        for item in order.get('items', []):
            draw.text((80, y_pos), f"  {item['quantity']}x {item['name']}", fill='black', font=font_small)
            y_pos += 30

        y_pos += 20
        priority = order.get('priority') or 'normal'
        draw.text((50, y_pos), f"Priority: {priority.upper()}", fill='black', font=font_medium)

        if order.get('delivery_time_window_start'):
            y_pos += 35
            start_str = order['delivery_time_window_start'].strftime("%Y-%m-%d %H:%M")
            end_str = order['delivery_time_window_end'].strftime("%Y-%m-%d %H:%M")
            draw.text((50, y_pos), f"Delivery Window: {start_str} to {end_str}", fill='black', font=font_small)

    else:
        # Poorly formatted order
        text_lines = [
            f"Order #{order['order_number']}",
            f"{order['customer_name']}",
            f"Phone: {order.get('customer_phone', 'N/A')}",
            f"{order['delivery_address']}",
            "",
            "Items:"
        ]

        for item in order.get('items', []):
            text_lines.append(f"  {item['quantity']} {item['name']}")

        text_lines.append("")
        text_lines.append(f"Priority: {order.get('priority', 'normal')}")

        for line in text_lines:
            draw.text((50, y_pos), line, fill='black', font=font_small)
            y_pos += 28

    filename = f"{order['order_number']}.png"
    filepath = output_dir / filename
    img.save(filepath)
    return filepath


def create_text_order(order: Dict, output_dir: Path, format_type: str = "well_formatted"):
    """Create a plain text order for email body"""
    filename = f"{order['order_number']}.txt"
    filepath = output_dir / filename

    if format_type == "well_formatted":
        text = f"""ORDER FORM

Order Number: {order['order_number']}
Customer Name: {order['customer_name']}
"""
        if order.get('customer_email'):
            text += f"Email: {order['customer_email']}\n"
        if order.get('customer_phone'):
            text += f"Phone: {order['customer_phone']}\n"

        text += f"""
Delivery Address: {order['delivery_address']}
"""
        if order.get('description'):
            text += f"Description: {order['description']}\n"
        text += """
Items:
"""
        for item in order.get('items', []):
            text += f"  {item['quantity']}x {item['name']}\n"

        priority = order.get('priority') or 'normal'
        text += f"\nPriority: {priority.upper()}\n"

        if order.get('delivery_time_window_start'):
            start_str = order['delivery_time_window_start'].strftime("%Y-%m-%d %H:%M")
            end_str = order['delivery_time_window_end'].strftime("%Y-%m-%d %H:%M")
            text += f"Delivery Window: {start_str} to {end_str}\n"
    else:
        text = f"""Order #{order['order_number']}
{order['customer_name']}
Phone: {order.get('customer_phone', 'N/A')}
{order['delivery_address']}

Items:
"""
        for item in order.get('items', []):
            text += f"  {item['quantity']} {item['name']}\n"

        text += f"\nPriority: {order.get('priority', 'normal')}\n"

    with open(filepath, 'w') as f:
        f.write(text)

    return filepath


def main():
    """Generate all mock order documents"""
    # Create output directory
    script_dir = Path(__file__).parent
    output_dir = script_dir / "mock_orders"
    output_dir.mkdir(exist_ok=True)

    # Create subdirectories
    pdf_dir = output_dir / "pdfs"
    pdf_dir.mkdir(exist_ok=True)

    image_dir = output_dir / "images"
    image_dir.mkdir(exist_ok=True)

    text_dir = output_dir / "text"
    text_dir.mkdir(exist_ok=True)

    print("Generating mock orders...")

    generated_files = []

    # Generate order numbers in the new format (ORD-ddmmyy-XXXX)
    now = datetime.now()
    date_str = now.strftime("%d%m%y")  # ddmmyy format
    seq = 1

    for order in MOCK_ORDERS:
        # Generate order number if not set
        if not order.get('order_number'):
            order['order_number'] = f"ORD-{date_str}-{seq:04d}"
            seq += 1

        format_type = order.get('format', 'well_formatted')

        # Generate PDF
        if REPORTLAB_AVAILABLE:
            pdf_path = create_pdf_order(order, pdf_dir, format_type)
            if pdf_path:
                generated_files.append(pdf_path)
                print(f"  Created PDF: {pdf_path}")

        # Generate image
        if PIL_AVAILABLE:
            img_path = create_image_order(order, image_dir, format_type)
            if img_path:
                generated_files.append(img_path)
                print(f"  Created image: {img_path}")

        # Generate text
        txt_path = create_text_order(order, text_dir, format_type)
        generated_files.append(txt_path)
        print(f"  Created text: {txt_path}")

    print(f"\nGenerated {len(generated_files)} mock order documents in {output_dir}")
    print("\nFiles created:")
    for file in generated_files:
        print(f"  - {file}")

    return output_dir


if __name__ == "__main__":
    main()
