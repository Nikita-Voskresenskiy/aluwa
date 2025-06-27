from datetime import datetime
from geoalchemy2 import WKTElement
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from models import Location, User, TrackSession  # Import Location model


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
    print('--here', )
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



async def get_locations_by_session(
        session: AsyncSession,
        session_id: int,
        limit: int = 100
) -> list[Location]:
    """
    Retrieves locations for a specific session.

    Args:
        session: Async SQLAlchemy session
        session_id: Session ID to filter by
        limit: Maximum number of records to return

    Returns:
        List of Location objects
    """
    result = await session.execute(
        select(Location)
        .where(Location.session_id == session_id)
        .order_by(Location.timestamp.desc())
        .limit(limit)
    )

    return result.scalars().all()