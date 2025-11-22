from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import uuid

from ..database import get_db, Order
from ..models import OrderCreate, OrderUpdate, Order as OrderModel
from ..services.order_parser import parse_order_from_text
from ..services.order_validator import validate_order

router = APIRouter(prefix="/api/orders", tags=["orders"])


@router.post("/", response_model=OrderModel)
def create_order(order: OrderCreate, db: Session = Depends(get_db)):
    """Create a new order"""
    if not order.order_number:
        order.order_number = f"ORD-{uuid.uuid4().hex[:8].upper()}"

    db_order = Order(**order.dict())
    db.add(db_order)
    db.commit()
    db.refresh(db_order)
    return db_order


@router.get("/", response_model=List[OrderModel])
def get_orders(
    status: Optional[str] = None,
    source: Optional[str] = None,
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

    orders = query.offset(skip).limit(limit).all()
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
    source: str = "email",
    db: Session = Depends(get_db)
):
    """Upload and parse order from document (email attachment, fax, mail scan)"""
    from ..services.order_parser import parse_document

    # Save uploaded file temporarily
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
            items=parsed_data.get("items"),
            delivery_time_window_start=parsed_data.get("delivery_time_window_start"),
            delivery_time_window_end=parsed_data.get("delivery_time_window_end"),
            priority=parsed_data.get("priority", "normal"),
            source=source,
            raw_text=parsed_data.get("raw_text")
        )

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
    text: str,
    source: str = "phone",
    db: Session = Depends(get_db)
):
    """Parse order from text (e.g., from phone call)"""
    try:
        parsed_data = parse_order_from_text(text)

        order_data = OrderCreate(
            order_number=parsed_data.get("order_number"),
            delivery_address=parsed_data.get("delivery_address", ""),
            customer_name=parsed_data.get("customer_name"),
            customer_phone=parsed_data.get("customer_phone"),
            customer_email=parsed_data.get("customer_email"),
            items=parsed_data.get("items"),
            delivery_time_window_start=parsed_data.get("delivery_time_window_start"),
            delivery_time_window_end=parsed_data.get("delivery_time_window_end"),
            priority=parsed_data.get("priority", "normal"),
            source=source,
            raw_text=text
        )

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
