import pytesseract
from PIL import Image
import re
from typing import Dict, Optional, List, Any
from datetime import datetime
import os

# Try to use OpenAI if available, otherwise use simple regex parsing
try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False


def extract_text_from_image(image_path: str) -> str:
    """Extract text from image using OCR"""
    try:
        image = Image.open(image_path)
        text = pytesseract.image_to_string(image)
        return text
    except Exception as e:
        raise Exception(f"Error extracting text from image: {e}")


def extract_text_from_pdf(pdf_path: str) -> str:
    """Extract text from PDF (basic implementation)"""
    # For a full implementation, you'd use pdfplumber or PyPDF2
    # For now, we'll return a placeholder
    try:
        # Try using pdfplumber if available
        try:
            import pdfplumber
            with pdfplumber.open(pdf_path) as pdf:
                text = ""
                for page in pdf.pages:
                    text += page.extract_text() or ""
                return text
        except ImportError:
            # Fallback to PyPDF2
            try:
                import PyPDF2
                with open(pdf_path, 'rb') as file:
                    reader = PyPDF2.PdfReader(file)
                    text = ""
                    for page in reader.pages:
                        text += page.extract_text()
                    return text
            except ImportError:
                raise Exception("No PDF library available. Install pdfplumber or PyPDF2")
    except Exception as e:
        raise Exception(f"Error extracting text from PDF: {e}")


async def parse_document(file_path: str) -> Dict[str, Any]:
    """
    Parse a document (image or PDF) and extract order information
    """
    file_ext = os.path.splitext(file_path)[1].lower()

    # Extract text based on file type
    if file_ext in ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff']:
        raw_text = extract_text_from_image(file_path)
    elif file_ext == '.pdf':
        raw_text = extract_text_from_pdf(file_path)
    else:
        raise Exception(f"Unsupported file type: {file_ext}")

    # Parse the extracted text
    return parse_order_from_text(raw_text, raw_text=raw_text)


def parse_order_from_text(text: str, raw_text: Optional[str] = None) -> Dict[str, Any]:
    """
    Parse order information from text using AI or regex patterns
    """
    if raw_text is None:
        raw_text = text

    # Try using OpenAI if available
    if OPENAI_AVAILABLE:
        try:
            return parse_with_openai(text)
        except Exception as e:
            print(f"OpenAI parsing failed, falling back to regex: {e}")

    # Fallback to regex-based parsing
    return parse_with_regex(text, raw_text)


def parse_with_openai(text: str) -> Dict[str, Any]:
    """Parse order using OpenAI API"""
    import os
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        raise Exception("OpenAI API key not found. Set OPENAI_API_KEY environment variable.")
    # OpenAI client will use OPENAI_API_KEY from environment if not passed explicitly
    client = openai.OpenAI()

    prompt = f"""Extract order information from the following text. Return a JSON object with these fields:
- order_number: Order number or ID if present
- customer_name: Customer's name
- customer_phone: Customer's phone number
- customer_email: Customer's email if present
- delivery_address: Full delivery address
- items: List of items with quantities (array of objects with 'name' and 'quantity')
- delivery_time_window_start: Delivery time start (ISO format) if specified
- delivery_time_window_end: Delivery time end (ISO format) if specified
- priority: Priority level (low, normal, high, urgent) if mentioned

Text to parse:
{text}

Return only valid JSON, no additional text."""

    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are an order parsing assistant. Extract order information and return valid JSON only."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.1
    )

    import json
    result_text = response.choices[0].message.content.strip()
    # Remove markdown code blocks if present
    if result_text.startswith("```"):
        result_text = result_text.split("```")[1]
        if result_text.startswith("json"):
            result_text = result_text[4:]
        result_text = result_text.strip()

    parsed = json.loads(result_text)
    parsed["raw_text"] = text
    return parsed


def parse_with_regex(text: str, raw_text: str) -> Dict[str, Any]:
    """Parse order using regex patterns (fallback)"""
    result = {
        "raw_text": raw_text
    }

    # Extract order number
    order_patterns = [
        r'order[:\s#]+([A-Z0-9\-]+)',
        r'order\s+number[:\s]+([A-Z0-9\-]+)',
        r'#([A-Z0-9\-]{6,})',
    ]
    for pattern in order_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            result["order_number"] = match.group(1).strip()
            break

    # Extract email
    email_match = re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', text)
    if email_match:
        result["customer_email"] = email_match.group(0)

    # Extract phone
    phone_patterns = [
        r'phone[:\s]+([+\d\s\-\(\)]+)',
        r'tel[:\s]+([+\d\s\-\(\)]+)',
        r'(\+?\d{1,3}[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{4})',
    ]
    for pattern in phone_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            phone = re.sub(r'[^\d+]', '', match.group(1))
            if len(phone) >= 7:
                result["customer_phone"] = match.group(1).strip()
                break

    # Extract address (look for common address patterns)
    address_patterns = [
        r'address[:\s]+(.+?)(?:\n|delivery|phone|email|$)',
        r'deliver[yi]+[:\s]+(.+?)(?:\n|phone|email|$)',
        r'(\d+\s+[\w\s]+(?:street|st|avenue|ave|road|rd|boulevard|blvd|drive|dr|lane|ln|way|circle|cir)[\s,]+[\w\s,]+)',
    ]
    for pattern in address_patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if match:
            address = match.group(1).strip()
            # Clean up address
            address = re.sub(r'\s+', ' ', address)
            if len(address) > 10:  # Reasonable address length
                result["delivery_address"] = address
                break

    # Extract customer name (look for "name:" pattern or first line)
    name_match = re.search(r'name[:\s]+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)', text, re.IGNORECASE)
    if name_match:
        result["customer_name"] = name_match.group(1).strip()

    # Extract items (simple pattern matching)
    items = []
    item_patterns = [
        r'(\d+)\s*x?\s*([A-Za-z\s]+?)(?:\n|$)',
        r'([A-Za-z\s]+?)\s*[:\-]?\s*(\d+)',
    ]
    for pattern in item_patterns:
        matches = re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE)
        for match in matches:
            try:
                quantity = int(match.group(1)) if match.group(1).isdigit() else int(match.group(2))
                name = match.group(2) if match.group(1).isdigit() else match.group(1)
                if quantity > 0 and len(name.strip()) > 2:
                    items.append({"name": name.strip(), "quantity": quantity})
            except:
                pass
        if items:
            break

    if items:
        result["items"] = items

    # Set default priority
    if "urgent" in text.lower() or "asap" in text.lower():
        result["priority"] = "urgent"
    elif "high" in text.lower():
        result["priority"] = "high"
    elif "low" in text.lower():
        result["priority"] = "low"
    else:
        result["priority"] = "normal"

    # Ensure delivery_address exists (required field)
    if "delivery_address" not in result:
        # Try to extract any address-like string
        lines = text.split('\n')
        for line in lines:
            line = line.strip()
            if len(line) > 15 and any(word in line.lower() for word in ['street', 'road', 'avenue', 'drive', 'lane', 'way']):
                result["delivery_address"] = line
                break

        # Last resort: use first substantial line
        if "delivery_address" not in result:
            for line in lines:
                line = line.strip()
                if len(line) > 10:
                    result["delivery_address"] = line
                    break

    return result
