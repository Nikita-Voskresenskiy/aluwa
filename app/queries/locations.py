from datetime import datetime
from geoalchemy2 import WKTElement
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from models import Location, User, TrackSession  # Import Location model
from sqlalchemy import func, update
from sqlalchemy.sql.expression import CTE

from error_handlers import SessionAccessError
from queries.db_user_access import can_access_session

def calculate_segment_duration(start, end):
    return (end - start).total_seconds()

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
    """Calculate and return session statistics including:
    - distance_m_total (excluding paused points)
    - speed_mps_max (excluding paused points)
    - speed_mps_average (excluding paused points)
    - duration_s_active (excluding paused points)
    - duration_s_total (including all points)
    """
    if not await can_access_session(session, user_id, track_session_id):
        raise SessionAccessError("User has no access to this track session")

    # First ensure all speeds are calculated
    # await calculate_speeds_for_session(session, track_session_id, user_id)

    cte = (
        select(
            Location,
            func.lag(Location.is_paused, 1).over(
                partition_by=Location.session_id,
                order_by=Location.custom_timestamp.asc()
            ).label('lag_paused')
        )
        .where(Location.session_id == track_session_id)
        .cte('cte')
    )

    paused_segments_start = await session.execute(
        select(
            cte.c.custom_timestamp
        )
        .where(cte.c.is_paused == True)
        .where(cte.c.lag_paused == False)
    )
    paused_segments_start = paused_segments_start.scalars().all()

    paused_segments_end = await session.execute(
        select(
            cte.c.custom_timestamp
        )
        .where(cte.c.is_paused == False)
        .where(cte.c.lag_paused == True)
    )
    paused_segments_end = paused_segments_end.scalars().all()

    # Get ALL locations for total duration calculation
    all_locations = await session.execute(
        select(Location)
        .where(Location.session_id == track_session_id)
        .order_by(Location.custom_timestamp.asc())
    )
    all_locations = all_locations.scalars().all()

    paused_segments_duartion = 0
    if paused_segments_start:
        if (len(paused_segments_start) == len(paused_segments_end) + 1):
            last_paused_segment_end = all_locations[-1].custom_timestamp
            paused_segments_end.append(last_paused_segment_end)
        if (len(paused_segments_start) == len(paused_segments_end)):
            for start, end in zip(paused_segments_start, paused_segments_end):
                paused_segments_duartion += calculate_segment_duration(start, end)

    #'''
    # Get only active locations for other calculations
    active_locations = await session.execute(
        select(Location)
        .where(Location.session_id == track_session_id)
        .where(Location.is_paused == False)
        .order_by(Location.custom_timestamp.asc())
    )
    active_locations = active_locations.scalars().all()
    #'''

    # Initialize statistics
    stats = {
        'distance_m_total': 0.0,
        'speed_mps_max': 0.0,
        'speed_mps_average': 0.0,
        'duration_s_active': 0.0,
        'duration_s_total': 0.0
    }

    # Calculate total duration (all points)
    if len(all_locations) > 1:
        first_point = all_locations[0]
        last_point = all_locations[-1]
        stats['duration_s_total'] = (last_point.custom_timestamp - first_point.custom_timestamp).total_seconds()
        stats['duration_s_active'] = stats['duration_s_total'] - paused_segments_duartion

    # Calculate active statistics (non-paused points only)
    if len(active_locations) > 1:
        # Calculate active duration
        first_active = active_locations[0]
        last_active = active_locations[-1]


        # Calculate distance and speeds
        total_distance = 0.0
        speed_sum = 0.0
        max_speed = 0.0
        valid_speeds_count = 0

        for i in range(1, len(active_locations)):
            prev_loc = active_locations[i - 1]
            current_loc = active_locations[i]

            # Calculate distance between points
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

            # Use the current point's speed
            if current_loc.speed_mps is not None:
                speed_sum += current_loc.speed_mps
                if current_loc.speed_mps > max_speed:
                    max_speed = current_loc.speed_mps
                valid_speeds_count += 1

        stats['distance_m_total'] = total_distance
        stats['speed_mps_max'] = max_speed
        stats['speed_mps_average'] = total_distance / stats['duration_s_active'] if stats['duration_s_active'] else 0.0

    # Update the TrackSession record with these statistics
    await session.execute(
        update(TrackSession)
        .where(TrackSession.session_id == track_session_id)
        .values(
            distance_m_total=stats['distance_m_total'],
            speed_mps_max=stats['speed_mps_max'],
            speed_mps_average=stats['speed_mps_average'],
            duration_s_active=stats['duration_s_active'],
            duration_s_total=stats['duration_s_total']
        )
    )
    await session.commit()

    return stats
