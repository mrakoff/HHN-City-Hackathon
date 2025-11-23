import secrets

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional

from ..database import get_db, Driver
from ..models import DriverCreate, DriverUpdate, Driver as DriverModel

router = APIRouter(prefix="/api/drivers", tags=["drivers"])


def _generate_unique_driver_token(db: Session) -> str:
    token = secrets.token_urlsafe(16)
    while db.query(Driver).filter(Driver.access_code == token).first():
        token = secrets.token_urlsafe(16)
    return token


@router.post("/", response_model=DriverModel)
def create_driver(driver: DriverCreate, db: Session = Depends(get_db)):
    """Create a new driver"""
    driver_payload = driver.dict()
    if not driver_payload.get("access_code"):
        driver_payload["access_code"] = _generate_unique_driver_token(db)

    db_driver = Driver(**driver_payload)
    db.add(db_driver)
    db.commit()
    db.refresh(db_driver)
    return db_driver


@router.get("/", response_model=List[DriverModel])
def get_drivers(
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Get all drivers with optional status filter"""
    query = db.query(Driver)

    if status:
        query = query.filter(Driver.status == status)

    drivers = query.offset(skip).limit(limit).all()
    return drivers


@router.get("/{driver_id}", response_model=DriverModel)
def get_driver(driver_id: int, db: Session = Depends(get_db)):
    """Get a specific driver by ID"""
    driver = db.query(Driver).filter(Driver.id == driver_id).first()
    if not driver:
        raise HTTPException(status_code=404, detail="Driver not found")
    return driver


@router.put("/{driver_id}", response_model=DriverModel)
def update_driver(driver_id: int, driver_update: DriverUpdate, db: Session = Depends(get_db)):
    """Update a driver"""
    db_driver = db.query(Driver).filter(Driver.id == driver_id).first()
    if not db_driver:
        raise HTTPException(status_code=404, detail="Driver not found")

    update_data = driver_update.dict(exclude_unset=True)

    if "access_code" in update_data and not update_data.get("access_code"):
        update_data["access_code"] = _generate_unique_driver_token(db)

    for field, value in update_data.items():
        setattr(db_driver, field, value)

    db.commit()
    db.refresh(db_driver)
    return db_driver


@router.delete("/{driver_id}")
def delete_driver(driver_id: int, db: Session = Depends(get_db)):
    """Delete a driver"""
    db_driver = db.query(Driver).filter(Driver.id == driver_id).first()
    if not db_driver:
        raise HTTPException(status_code=404, detail="Driver not found")

    db.delete(db_driver)
    db.commit()
    return {"message": "Driver deleted successfully"}
