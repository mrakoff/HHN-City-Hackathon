import pytesseract
from PIL import Image
import re
from typing import Dict, Optional, List, Any
from datetime import datetime
import os

# Try to use Gemini if available, otherwise use simple regex parsing
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False


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

    # Try using Gemini if available
    if GEMINI_AVAILABLE:
        try:
            return parse_with_gemini(text)
        except Exception as e:
            print(f"Gemini parsing failed, falling back to regex: {e}")

    # Fallback to regex-based parsing
    return parse_with_regex(text, raw_text)


def parse_with_gemini(text: str) -> Dict[str, Any]:
    """Parse order using Google Gemini API"""
    import os
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        raise Exception("Gemini API key not found. Set GEMINI_API_KEY environment variable.")

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.5-flash')

    prompt = f"""Extract order information from the following text. Return a JSON object with these fields:
- order_number: Order number or ID if present (optional)
- customer_name: Customer's full name (optional)
- customer_phone: Customer's phone number (optional, include country code if mentioned)
- customer_email: Customer's email address if present (optional)
- delivery_address: Full delivery address including street, city, postal code, country (REQUIRED - try to extract even if incomplete)
- description: Order description, notes, or special instructions if present (optional)
- items: List of items with quantities (array of objects with 'name' and 'quantity', optional)
- delivery_time_window_start: Delivery time start in ISO format (YYYY-MM-DDTHH:MM:SS) if specified. If only date is mentioned, use 00:00:00. If format is "dd.mm.yyyy, HH:MM", convert to ISO. (optional)
- delivery_time_window_end: Delivery time end in ISO format (YYYY-MM-DDTHH:MM:SS) if specified. If only date is mentioned, use 23:59:59. If format is "dd.mm.yyyy, HH:MM", convert to ISO. (optional)
- priority: Priority level (low, normal, high, urgent) if mentioned (optional)

IMPORTANT:
- delivery_address is REQUIRED. If not found, set it to empty string "" and note what information is missing.
- Extract as much information as possible, even if incomplete.
- For dates in format "dd.mm.yyyy, HH:MM" or "dd.mm.yyyy, --:--", convert to ISO format.
- If time is not specified (--:--), use 00:00:00 for start and 23:59:59 for end.

Text to parse:
{text}

Return only valid JSON, no additional text."""

    response = model.generate_content(prompt)
    import json
    result_text = response.text.strip()

    # Remove markdown code blocks if present
    if result_text.startswith("```"):
        result_text = result_text.split("```")[1]
        if result_text.startswith("json"):
            result_text = result_text[4:]
        result_text = result_text.strip()

    parsed = json.loads(result_text)
    parsed["raw_text"] = text

    # Parse and normalize date formats (dd.mm.yyyy, HH:MM or dd.mm.yyyy, --:--)
    if parsed.get("delivery_time_window_start"):
        parsed["delivery_time_window_start"] = parse_date_string(parsed["delivery_time_window_start"])
    if parsed.get("delivery_time_window_end"):
        parsed["delivery_time_window_end"] = parse_date_string(parsed["delivery_time_window_end"])

    return parsed


def parse_date_string(date_str: str) -> Optional[str]:
    """
    Parse date string in various formats and return ISO format string.
    Handles formats like:
    - "dd.mm.yyyy, HH:MM"
    - "dd.mm.yyyy, --:--"
    - ISO format strings
    - Other common date formats
    """
    if not date_str or not isinstance(date_str, str):
        return None

    try:
        # Try parsing dd.mm.yyyy format
        if re.match(r'\d{1,2}\.\d{1,2}\.\d{4}', date_str):
            # Extract date part (before comma if present)
            date_part = date_str.split(',')[0].strip()
            time_part = None
            if ',' in date_str:
                time_part = date_str.split(',')[1].strip()

            # Parse dd.mm.yyyy
            day, month, year = date_part.split('.')
            dt = datetime(int(year), int(month), int(day))

            # Parse time if provided (not --:--)
            if time_part and time_part != '--:--' and ':' in time_part:
                try:
                    hour, minute = time_part.split(':')
                    dt = dt.replace(hour=int(hour), minute=int(minute))
                except:
                    pass  # Use default 00:00:00

            return dt.isoformat()
        else:
            # Try ISO format directly
            try:
                # Remove timezone if present for parsing
                clean_str = date_str.replace('Z', '+00:00')
                dt = datetime.fromisoformat(clean_str)
                return dt.isoformat()
            except:
                # Try common formats
                formats = [
                    '%Y-%m-%d %H:%M:%S',
                    '%Y-%m-%dT%H:%M:%S',
                    '%Y-%m-%d %H:%M',
                    '%Y-%m-%d',
                    '%d/%m/%Y %H:%M',
                    '%d/%m/%Y',
                ]
                for fmt in formats:
                    try:
                        dt = datetime.strptime(date_str, fmt)
                        return dt.isoformat()
                    except:
                        continue
                # If all else fails, return as-is (might already be ISO)
                return date_str
    except Exception as e:
        print(f"Error parsing date '{date_str}': {e}")
        return None


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
        r'deliver[yi]+\s+to[:\s]+(.+?)(?:\n|phone|email|$)',
        r'(\d+\s+[\w\s]+(?:street|st|avenue|ave|road|rd|boulevard|blvd|drive|dr|lane|ln|way|circle|cir)[\s,]+[\w\s,]+)',
        r'(\d+\s+[\w\s]+(?:straße|str|platz|pl|weg|allee|ring)[\s,]+[\w\s,]+)',  # German addresses
        r'([A-Z][a-z]+\s+(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Drive|Dr|Lane|Ln|Way|Circle|Cir|Platz|Straße)[\s,]+[\w\s,]+)',
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

    # Extract description/notes
    description_patterns = [
        r'description[:\s]+(.+?)(?:\n(?:items|priority|delivery|order|customer)|$)',
        r'notes[:\s]+(.+?)(?:\n(?:items|priority|delivery|order|customer)|$)',
        r'special\s+instructions?[:\s]+(.+?)(?:\n(?:items|priority|delivery|order|customer)|$)',
        r'instructions?[:\s]+(.+?)(?:\n(?:items|priority|delivery|order|customer)|$)',
    ]
    for pattern in description_patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE | re.DOTALL)
        if match:
            desc = match.group(1).strip()
            # Clean up description (remove extra whitespace)
            desc = re.sub(r'\s+', ' ', desc)
            if len(desc) > 5:  # Only if meaningful length
                result["description"] = desc
                break

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
        address_keywords = ['street', 'road', 'avenue', 'drive', 'lane', 'way', 'straße', 'platz', 'weg', 'allee', 'ring', 'str']
        for line in lines:
            line = line.strip()
            if len(line) > 15 and any(word in line.lower() for word in address_keywords):
                result["delivery_address"] = line
                break

        # Try to find lines with numbers followed by text (common address pattern)
        if "delivery_address" not in result:
            for line in lines:
                line = line.strip()
                # Pattern: number + text (e.g., "123 Main Street" or "Hauptstraße 123")
                if re.match(r'^(\d+\s+[\w\s]+|[\w\s]+\s+\d+)', line) and len(line) > 10:
                    result["delivery_address"] = line
                    break

        # Last resort: use first substantial line that looks like an address
        if "delivery_address" not in result:
            for line in lines:
                line = line.strip()
                # Skip lines that are clearly not addresses (emails, phones, etc.)
                if '@' in line or re.match(r'^\+?\d', line):
                    continue
                if len(line) > 10 and not line.lower().startswith(('order', 'customer', 'phone', 'email', 'item')):
                    result["delivery_address"] = line
                    break

    return result
