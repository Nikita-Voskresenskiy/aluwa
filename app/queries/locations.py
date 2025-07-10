from datetime import datetime
from geoalchemy2 import WKTElement
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from models import Location, User, TrackSession  # Import Location model
from sqlalchemy import func

from error_handlers import SessionAccessError
from queries.db_user_access import can_access_session



async def record_location(
    session: AsyncSession,
    session_id: int,
    user_id: int,  # Add telegram_id parameter
    latitude: float,
    longitude: float,
    custom_timestamp: datetime,
    is_paused: bool
) -> Location:
    """Create location record with authorization check"""
    if not await can_access_session(session, user_id, session_id):
        raise ValueError("User cannot add to this track session")

    point = WKTElement(f'POINT({longitude} {latitude})', srid=4326)
    timestamp = custom_timestamp if custom_timestamp else datetime.utcnow()

    new_location = Location(
        session_id=session_id,
        custom_timestamp=timestamp,
        geom=point,
        is_paused=is_paused
    )

    session.add(new_location)
    await session.commit()
    await session.refresh(new_location)
    return new_location

async def start_session(
        session: AsyncSession,
        user_id: int,
        start_timestamp: datetime,
        live_period: int
) -> TrackSession:

    new_session = TrackSession(
        user_id=user_id,
        start_timestamp=start_timestamp
    )
    session.add(new_session)
    await session.commit()
    await session.refresh(new_session)
    session_id = new_session.session_id
    return session_id



async def get_sessions_by_telegram_id(
        session: AsyncSession,
        user_id: int,
        #start_num: int = 0,
        #rows_num: int = 100
) -> list[TrackSession]:

    result = await session.execute(
        select(TrackSession)
        .where(TrackSession.user_id == user_id)
        .order_by(TrackSession.start_timestamp.asc())
        #.limit(start_num, rows_num)
    )

    return result.scalars().all()

async def get_coordinates_by_session_id(
    session: AsyncSession,
    track_session_id: int,
    user_id: int,
) -> list[Location]:
    if not await can_access_session(session, user_id, track_session_id):
        raise SessionAccessError("User has no access to this track session")

    result = await session.execute(
        select(
            func.ST_X(Location.geom).label('longitude'),
            func.ST_Y(Location.geom).label('latitude'),
            Location.custom_timestamp,
            Location.is_paused,
        )
        .where(Location.session_id == track_session_id)
        .order_by(Location.custom_timestamp.asc())
    )
    return result.all()


