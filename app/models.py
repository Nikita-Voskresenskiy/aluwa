from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey
from geoalchemy2 import Geometry
from database import Base


class Location(Base):
    __tablename__ = "locations"

    session_id = Column(Integer, primary_key=True, index=True)
    custom_timestamp = Column(DateTime(timezone=True), primary_key=True)
    #timestamp = Column(DateTime)
    # Using PostGIS geometry (Point type in this example)
    geom = Column(Geometry(geometry_type='POINT', srid=4326))
    is_paused = Column(Boolean)

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    telegram_id = Column(Integer, index=True)

class TrackSession(Base):
    __tablename__ = "track_sessions"

    session_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'), index=True)
    start_timestamp = Column(DateTime(timezone=True), primary_key=True)

