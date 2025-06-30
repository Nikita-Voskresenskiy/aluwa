from datetime import datetime
from geoalchemy2 import WKTElement
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from models import Location, User, TrackSession  # Import Location model
from sqlalchemy import func

async def record_location(
        session: AsyncSession,
        session_id: int,
        latitude: float,
        longitude: float,
        custom_timestamp: datetime,
        is_paused: bool
) -> Location:
    """
    Creates a new location record in the database.

    Args:
        session: Async SQLAlchemy session
        session_id: ID of the tracking session
        latitude: Latitude in decimal degrees (WGS84)
        longitude: Longitude in decimal degrees (WGS84)
        custom_timestamp: Optional specific timestamp (defaults to now)

    Returns:
        The created Location object
    """
    # Create a Point geometry (WGS84 SRID 4326)
    point = WKTElement(f'POINT({longitude} {latitude})', srid=4326)

    # Use current time if no timestamp provided
    timestamp = custom_timestamp if custom_timestamp else datetime.utcnow()

    # Create new location record
    new_location = Location(
        session_id=session_id,
        custom_timestamp=timestamp,
        geom=point,
        is_paused=is_paused
    )

    # Add to session and commit
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
        #start_num: int = 0,
        #rows_num: int = 100
) -> list[Location]:

    #check if user with telegram_id can acceesss track session with track_sesion_id
    r = await session.execute(
        select(TrackSession).join(User, TrackSession.user_id == User.id)
        .where(TrackSession.session_id == track_session_id)
        .where(User.telegram_id == telegram_id)
    )
    r1 = r.scalars().all()
    length = len(r1)

    if (length > 0):
        r = await session.execute(
            select(
                func.ST_X(Location.geom).label('longitude'),
                func.ST_Y(Location.geom).label('latitude'),
                Location.custom_timestamp,
                Location.is_paused,
            )
            .where(Location.session_id == track_session_id)
            .order_by(Location.custom_timestamp.asc())
            #.limit(start_num, rows_num)
        )
        return r.all()
    else:
        raise Exception("User has no access to track session")


