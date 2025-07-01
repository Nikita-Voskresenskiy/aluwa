from datetime import datetime
from geoalchemy2 import WKTElement
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from models import Location, User, TrackSession  # Import Location model
from sqlalchemy import func

from error_handlers import SessionAccessError

async def can_access_session(
    db: AsyncSession,
    telegram_id: int,
    session_id: int
) -> bool:
    """Check if user owns the track session"""
    result = await db.execute(
        select(TrackSession)
        .join(User, TrackSession.user_id == User.id)
        .where(TrackSession.session_id == session_id)
        .where(User.telegram_id == telegram_id)
    )
    return len(result.scalars().all()) > 0

async def record_location(
    session: AsyncSession,
    session_id: int,
    telegram_id: int,  # Add telegram_id parameter
    latitude: float,
    longitude: float,
    custom_timestamp: datetime,
    is_paused: bool
) -> Location:
    """Create location record with authorization check"""
    if not await can_access_session(session, telegram_id, session_id):
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
        telegram_id: int,
        start_timestamp: datetime,
        live_period: int
) -> TrackSession:
    r = await session.execute(
        select(User)
        .where(User.telegram_id == telegram_id)
    )
    length = len(r.all())
    if length == 0:
        new_user = User(
            telegram_id=telegram_id,
        )
        session.add(new_user)
        await session.commit()
        await session.refresh(new_user)
        user_id = new_user.id
    else:
        r = await session.execute(
            select(User)
            .where(User.telegram_id == telegram_id)
            .limit(1)
        )
        user_id = r.all()[0][0].id
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
        telegram_id: int,
        #start_num: int = 0,
        #rows_num: int = 100
) -> list[TrackSession]:

    result = await session.execute(
        select(TrackSession)
        .join(User, TrackSession.user_id == User.id)
        .where(User.telegram_id == telegram_id)
        .order_by(TrackSession.start_timestamp.asc())
        #.limit(start_num, rows_num)
    )

    return result.scalars().all()

async def get_coordinates_by_session_id(
    session: AsyncSession,
    track_session_id: int,
    telegram_id: int,
) -> list[Location]:
    if not await can_access_session(session, telegram_id, track_session_id):
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


