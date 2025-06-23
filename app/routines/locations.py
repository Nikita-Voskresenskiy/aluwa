from datetime import datetime
from geoalchemy2 import WKTElement
from sqlalchemy.orm import Session
from database import SessionLocal
from models import Location
from typing import List, Optional
from sqlalchemy.exc import SQLAlchemyError

# routines/locations.py (example)
def create_location(db: Session, session_id: int, latitude: float, longitude: float, custom_timestamp=None):
    # Your implementation here
    # Example:
    new_location = Location(
        session_id=session_id,
        geom=f"POINT({longitude} {latitude})",
        timestamp=custom_timestamp or datetime.utcnow()
    )
    db.add(new_location)
    return new_location

def get_locations_by_session(db: Session, session_id: int):
    # Your implementation here
    return db.query(Location).filter(Location.session_id == session_id).all()