from sqlalchemy import Column, Integer, String, DateTime
from geoalchemy2 import Geometry
from database import Base


class Location(Base):
    __tablename__ = "locations"

    session_id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, primary_key=True)
    # Using PostGIS geometry (Point type in this example)
    geom = Column(Geometry(geometry_type='POINT', srid=4326))