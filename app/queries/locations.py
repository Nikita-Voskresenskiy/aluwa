from datetime import datetime
from geoalchemy2 import WKTElement
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from models import Location, User, TrackSession  # Import Location model
from sqlalchemy import func, update

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



async def get_sessions_by_user_id(
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
            Location.speed_mps
        )
        .where(Location.session_id == track_session_id)
        .order_by(Location.custom_timestamp.asc())
    )
    return result.all()


async def calculate_speeds_for_session(
        session: AsyncSession,
        track_session_id: int,
        user_id: int,
) -> None:
    """Calculate and update speeds for all points in a session"""
    if not await can_access_session(session, user_id, track_session_id):
        raise SessionAccessError("User has no access to this track session")

    # Get all locations for the session ordered by timestamp
    locations = await session.execute(
        select(Location)
        .where(Location.session_id == track_session_id)
        .order_by(Location.custom_timestamp.asc())
    )
    locations = locations.scalars().all()

    # Calculate speeds for each point (except the first one)
    for i in range(1, len(locations)):
        prev_loc = locations[i - 1]
        current_loc = locations[i]

        # Skip if either point is paused
        if prev_loc.is_paused or current_loc.is_paused:
            current_loc.speed_mps = 0.0
            continue

        # Calculate time difference in seconds
        time_diff = (current_loc.custom_timestamp - prev_loc.custom_timestamp).total_seconds()
        if time_diff <= 0:
            current_loc.speed_mps = 0.0
            continue

        # Calculate distance using PostGIS function
        distance_result = await session.execute(
            select(
                func.ST_DistanceSphere(
                    prev_loc.geom,
                    current_loc.geom
                )
            )
        )
        distance_m = distance_result.scalar_one()

        # Calculate speed in meters per second
        speed_mps = distance_m / time_diff
        current_loc.speed_mps = speed_mps

    # The first point has no speed (or could set to 0)
    if len(locations) > 0:
        locations[0].speed_mps = 0.0

    await session.commit()


async def calculate_session_statistics(
        session: AsyncSession,
        track_session_id: int,
        user_id: int,
) -> dict:
    """Calculate and return session statistics (distance, max speed, avg speed) excluding paused points"""
    if not await can_access_session(session, user_id, track_session_id):
        raise SessionAccessError("User has no access to this track session")

    # First ensure all speeds are calculated
    await calculate_speeds_for_session(session, track_session_id, user_id)

    # Get all non-paused locations for the session ordered by timestamp
    locations = await session.execute(
        select(Location)
        .where(Location.session_id == track_session_id)
        .where(Location.is_paused == False)
        .order_by(Location.custom_timestamp.asc())
    )
    locations = locations.scalars().all()

    if len(locations) < 2:
        # Not enough points to calculate meaningful statistics
        return {
            'distance_m_total': 0.0,
            'speed_mps_max': 0.0,
            'speed_mps_average': 0.0
        }

    total_distance = 0.0
    speed_sum = 0.0
    max_speed = 0.0
    valid_speeds_count = 0

    # Calculate distances and speeds between consecutive points
    for i in range(1, len(locations)):
        prev_loc = locations[i - 1]
        current_loc = locations[i]

        # Calculate distance using PostGIS function
        distance_result = await session.execute(
            select(
                func.ST_DistanceSphere(
                    prev_loc.geom,
                    current_loc.geom
                )
            )
        )
        segment_distance = distance_result.scalar_one()
        total_distance += segment_distance

        # Use the current point's speed (already calculated)
        if current_loc.speed_mps is not None:
            speed_sum += current_loc.speed_mps
            if current_loc.speed_mps > max_speed:
                max_speed = current_loc.speed_mps
            valid_speeds_count += 1

    # Calculate average speed (avoid division by zero)
    avg_speed = speed_sum / valid_speeds_count if valid_speeds_count > 0 else 0.0

    # Update the TrackSession record with these statistics
    await session.execute(
        update(TrackSession)
        .where(TrackSession.session_id == track_session_id)
        .values(
            distance_m_total=total_distance,
            speed_mps_max=max_speed,
            speed_mps_average=avg_speed
        )
    )
    await session.commit()

    return {
        'distance_m_total': total_distance,
        'speed_mps_max': max_speed,
        'speed_mps_average': avg_speed
    }
