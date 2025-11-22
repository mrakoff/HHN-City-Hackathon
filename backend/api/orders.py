from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from sqlalchemy import or_, case
from typing import List, Optional
from datetime import datetime
import re

from ..database import get_db, Order
from ..models import OrderCreate, OrderUpdate, Order as OrderModel, ParseTextRequest
from ..services.order_parser import parse_order_from_text
from ..services.order_validator import validate_order, calculate_priority_from_time_window

router = APIRouter(prefix="/api/orders", tags=["orders"])


def generate_order_number(db: Session) -> str:
    """Generate order number in format ORD-ddmmyy-XXXX"""
    now = datetime.now()
    date_str = now.strftime("%d%m%y")  # ddmmyy format

    # Find the highest sequential number for today
    prefix = f"ORD-{date_str}-"

    # Query all orders with today's prefix
    existing_orders = db.query(Order.order_number).filter(
        Order.order_number.like(f"{prefix}%")
    ).all()

    max_seq = 0
    for order_num_tuple in existing_orders:
        order_num = order_num_tuple[0]
        # Extract the 4-digit sequence number
        match = re.search(rf"^{re.escape(prefix)}(\d{{4}})$", order_num)
        if match:
            seq_num = int(match.group(1))
            max_seq = max(max_seq, seq_num)

    # Increment and format as 4-digit zero-padded number
    next_seq = max_seq + 1
    return f"{prefix}{next_seq:04d}"


def ensure_unique_order_number(order_data: OrderCreate, db: Session) -> OrderCreate:
    """Ensure order_number is unique, generate new one if missing or conflicting"""
    if not order_data.order_number:
        # Generate a new order number if none provided
        order_data.order_number = generate_order_number(db)
    else:
        # Check if the provided order number already exists
        existing_order = db.query(Order).filter(Order.order_number == order_data.order_number).first()
        if existing_order:
            # Generate a new unique order number in the correct format
            order_data.order_number = generate_order_number(db)
    return order_data


@router.post("/", response_model=OrderModel)
def create_order(order: OrderCreate, db: Session = Depends(get_db)):
    """Create a new order"""
    if not order.order_number:
        order.order_number = generate_order_number(db)

    # Calculate priority if not explicitly set
    if not order.priority:
        order.priority = calculate_priority_from_time_window(
            order.delivery_time_window_start,
            order.delivery_time_window_end
        )

    db_order = Order(**order.dict())
    db.add(db_order)
    db.commit()
    db.refresh(db_order)
    return db_order


@router.get("/", response_model=List[OrderModel])
def get_orders(
    status: Optional[str] = None,
    source: Optional[str] = None,
    unfinished: Optional[bool] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Get all orders with optional filters"""
    query = db.query(Order)

    if status:
        query = query.filter(Order.status == status)
    if source:
        query = query.filter(Order.source == source)
    if unfinished is not None and unfinished:
        # Unfinished orders: have validation errors or missing critical fields
        query = query.filter(
            or_(
                # Has validation errors (not None - empty lists will be filtered in Python)
                Order.validation_errors.isnot(None),
                # Missing delivery address
                Order.delivery_address == None,
                Order.delivery_address == ""
            )
        )

    # Sort orders: priority first (urgent > high > normal > low), then by created_at (newest first)
    # Apply sorting
    query = query.order_by(
        # Sort by priority (custom order)
        case(
            (Order.priority == 'urgent', 1),
            (Order.priority == 'high', 2),
            (Order.priority == 'normal', 3),
            (Order.priority == 'low', 4),
            else_=5  # Unknown/null priority goes last
        ),
        # Then by created_at descending (newest first)
        Order.created_at.desc()
    )

    orders = query.offset(skip).limit(limit).all()

    # Filter out orders with empty validation_errors lists (they're not unfinished)
    if unfinished is not None and unfinished:
        orders = [
            order for order in orders
            if (
                # Has non-empty validation errors
                (order.validation_errors is not None and
                 isinstance(order.validation_errors, list) and
                 len(order.validation_errors) > 0) or
                # Missing delivery address
                not order.delivery_address or
                order.delivery_address.strip() == ""
            )
        ]

    return orders


@router.get("/{order_id}", response_model=OrderModel)
def get_order(order_id: int, db: Session = Depends(get_db)):
    """Get a specific order by ID"""
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@router.put("/{order_id}", response_model=OrderModel)
def update_order(order_id: int, order_update: OrderUpdate, db: Session = Depends(get_db)):
    """Update an order"""
    db_order = db.query(Order).filter(Order.id == order_id).first()
    if not db_order:
        raise HTTPException(status_code=404, detail="Order not found")

    update_data = order_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_order, field, value)

    db_order.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(db_order)
    return db_order


@router.delete("/{order_id}")
def delete_order(order_id: int, db: Session = Depends(get_db)):
    """Delete an order"""
    db_order = db.query(Order).filter(Order.id == order_id).first()
    if not db_order:
        raise HTTPException(status_code=404, detail="Order not found")

    db.delete(db_order)
    db.commit()
    return {"message": "Order deleted successfully"}


@router.post("/upload", response_model=OrderModel)
async def upload_order_document(
    file: UploadFile = File(...),
    source: str = Form("email"),
    db: Session = Depends(get_db)
):
    """Upload and parse order from document (email attachment, fax, mail scan)"""
    from ..services.order_parser import parse_document

    # Save uploaded file temporarily
    import aiofiles
    import os
    from pathlib import Path
    import uuid

    os.makedirs("uploads", exist_ok=True)
    # Use a unique filename to avoid conflicts and path traversal issues
    safe_filename = os.path.basename(file.filename) if file.filename else "upload"
    file_ext = Path(safe_filename).suffix
    unique_filename = f"{uuid.uuid4().hex}{file_ext}"
    file_path = os.path.join("uploads", unique_filename)

    async with aiofiles.open(file_path, 'wb') as out_file:
        content = await file.read()
        await out_file.write(content)

    # Parse document
    try:
        parsed_data = await parse_document(file_path)

        # Create order from parsed data
        order_data = OrderCreate(
            order_number=parsed_data.get("order_number"),
            delivery_address=parsed_data.get("delivery_address", ""),
            customer_name=parsed_data.get("customer_name"),
            customer_phone=parsed_data.get("customer_phone"),
            customer_email=parsed_data.get("customer_email"),
            description=parsed_data.get("description"),
            items=parsed_data.get("items"),
            delivery_time_window_start=parsed_data.get("delivery_time_window_start"),
            delivery_time_window_end=parsed_data.get("delivery_time_window_end"),
            priority=None,  # Will be calculated automatically
            source=source,
            raw_text=parsed_data.get("raw_text")
        )

        # Calculate priority based on time window
        order_data.priority = calculate_priority_from_time_window(
            order_data.delivery_time_window_start,
            order_data.delivery_time_window_end,
            parsed_data.get("priority")
        )

        # Ensure unique order number (generate if missing - should always happen)
        order_data = ensure_unique_order_number(order_data, db)

        # Validate order
        validation_errors = validate_order(order_data)

        db_order = Order(**order_data.dict())
        if validation_errors:
            db_order.validation_errors = validation_errors

        db.add(db_order)
        db.commit()
        db.refresh(db_order)

        # Clean up uploaded file
        os.remove(file_path)

        return db_order

    except Exception as e:
        # Clean up on error
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=400, detail=f"Error parsing document: {str(e)}")


@router.post("/parse-text", response_model=OrderModel)
def parse_order_text(
    request: ParseTextRequest,
    db: Session = Depends(get_db)
):
    """Parse order from text (e.g., from phone call)"""
    try:
        text = request.text
        source = request.source
        parsed_data = parse_order_from_text(text)

        order_data = OrderCreate(
            order_number=parsed_data.get("order_number"),
            delivery_address=parsed_data.get("delivery_address", ""),
            customer_name=parsed_data.get("customer_name"),
            customer_phone=parsed_data.get("customer_phone"),
            customer_email=parsed_data.get("customer_email"),
            description=parsed_data.get("description"),
            items=parsed_data.get("items"),
            delivery_time_window_start=parsed_data.get("delivery_time_window_start"),
            delivery_time_window_end=parsed_data.get("delivery_time_window_end"),
            priority=None,  # Will be calculated automatically
            source=source,
            raw_text=text
        )

        # Calculate priority based on time window
        order_data.priority = calculate_priority_from_time_window(
            order_data.delivery_time_window_start,
            order_data.delivery_time_window_end,
            parsed_data.get("priority")
        )

        # Ensure unique order number (generate if missing - should always happen)
        order_data = ensure_unique_order_number(order_data, db)

        # Validate order
        validation_errors = validate_order(order_data)

        db_order = Order(**order_data.dict())
        if validation_errors:
            db_order.validation_errors = validation_errors

        db.add(db_order)
        db.commit()
        db.refresh(db_order)

        return db_order

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error parsing text: {str(e)}")


@router.post("/transcribe-audio")
async def transcribe_audio_chunk(
    audio: UploadFile = File(...),
    language: Optional[str] = Form(None)
):
    """Transcribe an audio chunk using local Whisper model (no API key needed)
    Uses the open-source Whisper model running locally on the server.
    """
    from ..services.speech_to_text import transcribe_audio_bytes
    import traceback

    try:
        # Read audio file content
        audio_bytes = await audio.read()
        filename = audio.filename or "audio.webm"

        if len(audio_bytes) == 0:
            raise HTTPException(status_code=400, detail="Empty audio file received")

        print(f"Received audio file: {filename}, size: {len(audio_bytes)} bytes")

        # Transcribe audio using local Whisper model
        transcription = transcribe_audio_bytes(audio_bytes, filename=filename, language=language)

        return {
            "transcription": transcription,
            "success": True
        }
    except HTTPException:
        raise
    except Exception as e:
        error_detail = str(e)
        error_trace = traceback.format_exc()
        print(f"Transcription error: {error_detail}")
        print(f"Traceback: {error_trace}")

        # Return user-friendly error message
        if "corrupted" in error_detail.lower() or "incomplete" in error_detail.lower() or "invalid data" in error_detail.lower():
            user_message = "The audio recording could not be processed. Please try recording again and make sure to speak clearly."
        elif "too small" in error_detail.lower() or "too short" in error_detail.lower():
            user_message = "The recording is too short. Please record for at least a few seconds."
        else:
            user_message = "Unable to transcribe the audio. Please try recording again."

        raise HTTPException(
            status_code=500,
            detail=user_message
        )


@router.post("/transcribe-audio-final")
async def transcribe_audio_final(
    audio: UploadFile = File(...),
    language: Optional[str] = Form(None)
):
    """Transcribe complete audio file and return full transcription"""
    from ..services.speech_to_text import transcribe_audio_bytes

    try:
        # Read audio file content
        audio_bytes = await audio.read()
        filename = audio.filename or "audio.webm"

        # Transcribe audio
        transcription = transcribe_audio_bytes(audio_bytes, filename=filename, language=language)

        return {
            "transcription": transcription,
            "success": True
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error transcribing audio: {str(e)}")


@router.post("/receive-email", response_model=OrderModel)
async def receive_email_order(
    sender_email: Optional[str] = Form(None),
    email_body: Optional[str] = Form(None),
    attachment: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    """Simulate receiving an order via email with optional attachment"""
    from ..services.order_parser import parse_document
    import aiofiles
    import os

    parsed_data = None
    file_path = None

    try:
        # If there's an attachment, parse it
        if attachment:
            os.makedirs("uploads", exist_ok=True)
            file_path = f"uploads/{attachment.filename}"

            async with aiofiles.open(file_path, 'wb') as out_file:
                content = await attachment.read()
                await out_file.write(content)

            parsed_data = await parse_document(file_path)

            # Clean up uploaded file
            if os.path.exists(file_path):
                os.remove(file_path)
                file_path = None
        # Otherwise, parse email body text
        elif email_body:
            parsed_data = parse_order_from_text(email_body)
        else:
            raise HTTPException(status_code=400, detail="Either attachment or email_body must be provided")

        # Create order from parsed data
        order_data = OrderCreate(
            order_number=parsed_data.get("order_number"),
            delivery_address=parsed_data.get("delivery_address", ""),
            customer_name=parsed_data.get("customer_name"),
            customer_phone=parsed_data.get("customer_phone"),
            customer_email=sender_email or parsed_data.get("customer_email"),
            description=parsed_data.get("description"),
            items=parsed_data.get("items"),
            delivery_time_window_start=parsed_data.get("delivery_time_window_start"),
            delivery_time_window_end=parsed_data.get("delivery_time_window_end"),
            priority=None,  # Will be calculated automatically
            source="email",
            raw_text=parsed_data.get("raw_text") or email_body
        )

        # Calculate priority based on time window
        order_data.priority = calculate_priority_from_time_window(
            order_data.delivery_time_window_start,
            order_data.delivery_time_window_end,
            parsed_data.get("priority")
        )

        # Ensure unique order number (generate if missing - should always happen)
        order_data = ensure_unique_order_number(order_data, db)

        # Validate order
        validation_errors = validate_order(order_data)

        db_order = Order(**order_data.dict())
        if validation_errors:
            db_order.validation_errors = validation_errors

        db.add(db_order)
        db.commit()
        db.refresh(db_order)

        return db_order

    except HTTPException:
        raise
    except Exception as e:
        # Clean up on error
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=400, detail=f"Error processing email order: {str(e)}")


@router.post("/receive-fax", response_model=OrderModel)
async def receive_fax_order(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Simulate receiving an order via fax"""
    from ..services.order_parser import parse_document
    import aiofiles
    import os

    os.makedirs("uploads", exist_ok=True)
    file_path = f"uploads/{file.filename}"

    async with aiofiles.open(file_path, 'wb') as out_file:
        content = await file.read()
        await out_file.write(content)

    # Parse document
    try:
        parsed_data = await parse_document(file_path)

        # Create order from parsed data
        order_data = OrderCreate(
            order_number=parsed_data.get("order_number"),
            delivery_address=parsed_data.get("delivery_address", ""),
            customer_name=parsed_data.get("customer_name"),
            customer_phone=parsed_data.get("customer_phone"),
            customer_email=parsed_data.get("customer_email"),
            description=parsed_data.get("description"),
            items=parsed_data.get("items"),
            delivery_time_window_start=parsed_data.get("delivery_time_window_start"),
            delivery_time_window_end=parsed_data.get("delivery_time_window_end"),
            priority=None,  # Will be calculated automatically
            source="fax",
            raw_text=parsed_data.get("raw_text")
        )

        # Calculate priority based on time window
        order_data.priority = calculate_priority_from_time_window(
            order_data.delivery_time_window_start,
            order_data.delivery_time_window_end,
            parsed_data.get("priority")
        )

        # Ensure unique order number (generate if missing - should always happen)
        order_data = ensure_unique_order_number(order_data, db)

        # Validate order
        validation_errors = validate_order(order_data)

        db_order = Order(**order_data.dict())
        if validation_errors:
            db_order.validation_errors = validation_errors

        db.add(db_order)
        db.commit()
        db.refresh(db_order)

        # Clean up uploaded file
        os.remove(file_path)

        return db_order

    except Exception as e:
        # Clean up on error
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=400, detail=f"Error parsing fax document: {str(e)}")


@router.post("/receive-mail", response_model=OrderModel)
async def receive_mail_order(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Simulate receiving an order via scanned physical mail"""
    from ..services.order_parser import parse_document
    import aiofiles
    import os

    os.makedirs("uploads", exist_ok=True)
    file_path = f"uploads/{file.filename}"

    async with aiofiles.open(file_path, 'wb') as out_file:
        content = await file.read()
        await out_file.write(content)

    # Parse document
    try:
        parsed_data = await parse_document(file_path)

        # Create order from parsed data
        order_data = OrderCreate(
            order_number=parsed_data.get("order_number"),
            delivery_address=parsed_data.get("delivery_address", ""),
            customer_name=parsed_data.get("customer_name"),
            customer_phone=parsed_data.get("customer_phone"),
            customer_email=parsed_data.get("customer_email"),
            description=parsed_data.get("description"),
            items=parsed_data.get("items"),
            delivery_time_window_start=parsed_data.get("delivery_time_window_start"),
            delivery_time_window_end=parsed_data.get("delivery_time_window_end"),
            priority=None,  # Will be calculated automatically
            source="mail",
            raw_text=parsed_data.get("raw_text")
        )

        # Calculate priority based on time window
        order_data.priority = calculate_priority_from_time_window(
            order_data.delivery_time_window_start,
            order_data.delivery_time_window_end,
            parsed_data.get("priority")
        )

        # Ensure unique order number (generate if missing - should always happen)
        order_data = ensure_unique_order_number(order_data, db)

        # Validate order
        validation_errors = validate_order(order_data)

        db_order = Order(**order_data.dict())
        if validation_errors:
            db_order.validation_errors = validation_errors

        db.add(db_order)
        db.commit()
        db.refresh(db_order)

        # Clean up uploaded file
        os.remove(file_path)

        return db_order

    except Exception as e:
        # Clean up on error
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=400, detail=f"Error parsing mail document: {str(e)}")
