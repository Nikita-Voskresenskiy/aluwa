from sqlalchemy import Column, Integer, Float, String, DateTime, Boolean, ForeignKey
from geoalchemy2 import Geometry
from database import Base


class Location(Base):
    __tablename__ = "locations"

    track_id = Column(Integer, ForeignKey('tracks.track_id'), primary_key=True, index=True)
    custom_timestamp = Column(DateTime(timezone=True), primary_key=True)
    geom = Column(Geometry(geometry_type='POINT', srid=4326))
    is_paused = Column(Boolean)
    speed_mps = Column(Float)

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    telegram_id = Column(Integer, index=True)

class Track(Base):
    __tablename__ = "tracks"

    track_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'), index=True)
    start_timestamp = Column(DateTime(timezone=True))
    distance_m_total = Column(Float)
    speed_mps_max = Column(Float)
    speed_mps_average = Column(Float)
    duration_s_active = Column(Float)
    duration_s_total = Column(Float)
