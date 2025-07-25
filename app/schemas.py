from pydantic import BaseModel
from datetime import datetime

class RecordLocation(BaseModel):
    track_id: int
    latitude: float
    longitude: float
    device_timestamp: datetime
    is_paused: bool

class CreateTrack(BaseModel):
    live_period: int
    start_timestamp: datetime

class StopTrack(BaseModel):
    track_id: int