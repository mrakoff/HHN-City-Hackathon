from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional

from ..database import get_db, Depot, ParkingLocation
from ..models import (
    DepotCreate, Depot as DepotModel,
    ParkingLocationCreate, ParkingLocation as ParkingLocationModel
)
from ..services.geocoding import geocode_address

router = APIRouter(prefix="/api/locations", tags=["locations"])


# Depot endpoints
@router.post("/depots", response_model=DepotModel)
def create_depot(depot: DepotCreate, db: Session = Depends(get_db)):
    """Create a new depot"""
    depot_data = depot.dict()

    # Geocode if coordinates not provided
    if not depot_data.get("latitude") or not depot_data.get("longitude"):
        coords = geocode_address(depot.address)
        if coords:
            depot_data["latitude"] = coords["lat"]
            depot_data["longitude"] = coords["lon"]

    db_depot = Depot(**depot_data)
    db.add(db_depot)
    db.commit()
    db.refresh(db_depot)
    return db_depot


@router.get("/depots", response_model=List[DepotModel])
def get_depots(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """Get all depots"""
    depots = db.query(Depot).offset(skip).limit(limit).all()
    return depots


@router.get("/depots/{depot_id}", response_model=DepotModel)
def get_depot(depot_id: int, db: Session = Depends(get_db)):
    """Get a specific depot by ID"""
    depot = db.query(Depot).filter(Depot.id == depot_id).first()
    if not depot:
        raise HTTPException(status_code=404, detail="Depot not found")
    return depot


@router.delete("/depots/{depot_id}")
def delete_depot(depot_id: int, db: Session = Depends(get_db)):
    """Delete a depot"""
    depot = db.query(Depot).filter(Depot.id == depot_id).first()
    if not depot:
        raise HTTPException(status_code=404, detail="Depot not found")

    db.delete(depot)
    db.commit()
    return {"message": "Depot deleted successfully"}


# Parking location endpoints
@router.post("/parking", response_model=ParkingLocationModel)
def create_parking_location(
    parking: ParkingLocationCreate,
    db: Session = Depends(get_db)
):
    """Create a new parking location"""
    parking_data = parking.dict()

    # Geocode if coordinates not provided
    if not parking_data.get("latitude") or not parking_data.get("longitude"):
        coords = geocode_address(parking.address)
        if coords:
            parking_data["latitude"] = coords["lat"]
            parking_data["longitude"] = coords["lon"]

    db_parking = ParkingLocation(**parking_data)
    db.add(db_parking)
    db.commit()
    db.refresh(db_parking)
    return db_parking


@router.get("/parking", response_model=List[ParkingLocationModel])
def get_parking_locations(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Get all parking locations"""
    parking_locations = db.query(ParkingLocation).offset(skip).limit(limit).all()
    return parking_locations


@router.get("/parking/{parking_id}", response_model=ParkingLocationModel)
def get_parking_location(parking_id: int, db: Session = Depends(get_db)):
    """Get a specific parking location by ID"""
    parking = db.query(ParkingLocation).filter(ParkingLocation.id == parking_id).first()
    if not parking:
        raise HTTPException(status_code=404, detail="Parking location not found")
    return parking


@router.delete("/parking/{parking_id}")
def delete_parking_location(parking_id: int, db: Session = Depends(get_db)):
    """Delete a parking location"""
    parking = db.query(ParkingLocation).filter(ParkingLocation.id == parking_id).first()
    if not parking:
        raise HTTPException(status_code=404, detail="Parking location not found")

    db.delete(parking)
    db.commit()
    return {"message": "Parking location deleted successfully"}
