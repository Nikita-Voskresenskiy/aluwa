from pydantic import BaseModel
from datetime import datetime

class LocationCreate(BaseModel):
    session_id: int
    latitude: float
    longitude: float
    device_timestamp: datetime = None