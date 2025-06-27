from pydantic import BaseModel
from datetime import datetime

class RecordLocation(BaseModel):
    session_id: int
    latitude: float
    longitude: float
    device_timestamp: datetime
    is_paused: bool

class CreateTrackSession(BaseModel):
    live_period: int
    start_timestamp: datetime