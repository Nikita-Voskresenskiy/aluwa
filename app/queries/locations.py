from datetime import datetime
from geoalchemy2 import WKTElement
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from models import Location, User, Track  # Import Location model
from sqlalchemy import func, update, Integer
from app_logger import logger

from error_handlers import SessionAccessError
from queries.db_user_access import can_access_track

def calculate_segment_duration(start, end):
    return (end - start).total_seconds()

async def record_location(
    session: AsyncSession,
    track_id: int,
    user_id: int,  # Add telegram_id parameter
    latitude: float,
    longitude: float,
    custom_timestamp: datetime,
    is_paused: bool
) -> Location:
    """Create location record with authorization check"""
    if not await can_access_track(session, user_id, track_id):
        raise ValueError("User cannot add to this track session")

    point = WKTElement(f'POINT({longitude} {latitude})', srid=4326)
    timestamp = custom_timestamp if custom_timestamp else datetime.utcnow()

    new_location = Location(
        track_id=track_id,
        custom_timestamp=timestamp,
        geom=point,
        is_paused=is_paused
    )

    session.add(new_location)
    await session.commit()
    await session.refresh(new_location)
    return new_location

async def start_track(
        session: AsyncSession,
        user_id: int,
        start_timestamp: datetime,
        live_period: int
) -> Track:

    new_track = Track(
        user_id=user_id,
        start_timestamp=start_timestamp
    )
    session.add(new_track)
    await session.commit()
    await session.refresh(new_track)
    track_id = new_track.track_id
    return track_id



async def get_tracks_by_user_id(
        session: AsyncSession,
        user_id: int,
        #start_num: int = 0,
        #rows_num: int = 100
) -> list[Track]:

    result = await session.execute(
        select(Track)
        .where(Track.user_id == user_id)
        .order_by(Track.start_timestamp.asc())
        #.limit(start_num, rows_num)
    )

    return result.scalars().all()

async def get_coordinates_by_track_id(
    session: AsyncSession,
    track_id: int,
    user_id: int,
) -> list[Location]:
    if not await can_access_track(session, user_id, track_id):
        raise SessionAccessError("User has no access to this track session")

    result = await session.execute(
        select(
            func.ST_X(Location.geom).label('longitude'),
            func.ST_Y(Location.geom).label('latitude'),
            Location.custom_timestamp,
            Location.is_paused,
            Location.speed_mps
        )
        .where(Location.track_id == track_id)
        .order_by(Location.custom_timestamp.asc())
    )
    return result.all()


async def calculate_speeds_for_track(
        session: AsyncSession,
        track_id: int,
        user_id: int,
) -> None:
    """Calculate and update speeds for all points in a session"""
    if not await can_access_track(session, user_id, track_id):
        raise SessionAccessError("User has no access to this track session")

    # Get all locations for the session ordered by timestamp
    locations = await session.execute(
        select(Location)
        .where(Location.track_id == track_id)
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


async def get_segments_statistics(
        session: AsyncSession,
        track_id: int,
        user_id: int,
) -> list[dict]:
    """Calculate segment statistics for a track using CTEs.

    Returns a list of dictionaries with segment statistics including:
    - segment_id: identifier for the segment
    - is_paused: whether the segment is paused
    - segment_distance: total distance in meters
    - duration: duration as timedelta


    with cte as
    (select
    locations.*,
    LAG(geom, 1, geom) over (partition by track_id order by custom_timestamp ASC) as geom_lagged,
    is_paused::int != LAG(is_paused::int, 1, 1) over (partition by track_id order by custom_timestamp ASC) as diff_paused
    from locations where track_id=17),
    cte2 as (select *,
    ST_DistanceSphere(cte.geom, cte.geom_lagged) as sph_dist,
    sum(diff_paused::int) over (partition by track_id order by custom_timestamp asc ROWS BETWEEN unbounded preceding and current row) as segment_id
    from cte order by custom_timestamp asc),
    cte3 as (select segment_id, is_paused,
    min(cte2.custom_timestamp) over (partition by segment_id order by custom_timestamp asc) as segment_start,
    max(cte2.custom_timestamp) over (partition by segment_id order by custom_timestamp asc) as segment_end,
    sum(cte2.sph_dist) over (partition by segment_id order by custom_timestamp asc) as segment_distance
    from cte2)
    select segment_id, is_paused, max(segment_distance) as segment_distance, max(segment_end-segment_start) as duration from cte3 group by segment_id, is_paused

    """
    if not await can_access_track(session, user_id, track_id):
        raise SessionAccessError("User has no access to this track session")

    # First CTE to get previous points and paused state changes
    cte1 = (
        select(
            Location,
            func.lag(Location.geom, 1, Location.geom).over(
                partition_by=Location.track_id,
                order_by=Location.custom_timestamp.asc()
            ).label('geom_lagged'),
            (Location.is_paused.cast(Integer) != func.lag(
                Location.is_paused.cast(Integer),
                1,
                1
            ).over(
                partition_by=Location.track_id,
                order_by=Location.custom_timestamp.asc()
            )).label('diff_paused')
        )
        .where(Location.track_id == track_id)
        .cte('cte1')
    )

    # Second CTE to calculate distances and segment IDs
    cte2 = (
        select(
            cte1,
            func.ST_DistanceSphere(cte1.c.geom, cte1.c.geom_lagged).label('sph_dist'),
            func.sum(cte1.c.diff_paused.cast(Integer)).over(
                partition_by=cte1.c.track_id,
                order_by=cte1.c.custom_timestamp.asc(),
                range_=(None, 0)
            ).label('segment_id')
        )
        .order_by(cte1.c.custom_timestamp.asc())
        .cte('cte2')
    )

    # Third CTE to calculate segment statistics
    cte3 = (
        select(
            cte2.c.segment_id,
            cte2.c.is_paused,
            func.min(cte2.c.custom_timestamp).over(
                partition_by=cte2.c.segment_id,
                order_by=cte2.c.custom_timestamp.asc()
            ).label('segment_start'),
            func.max(cte2.c.custom_timestamp).over(
                partition_by=cte2.c.segment_id,
                order_by=cte2.c.custom_timestamp.asc()
            ).label('segment_end'),
            func.sum(cte2.c.sph_dist).over(
                partition_by=cte2.c.segment_id,
                order_by=cte2.c.custom_timestamp.asc()
            ).label('segment_distance')
        )
        .cte('cte3')
    )

    # Final query to get aggregated segment statistics
    final_query = (
        select(
            cte3.c.segment_id,
            cte3.c.is_paused,
            func.max(cte3.c.segment_distance).label('segment_distance'),
            (func.max(cte3.c.segment_end) - func.min(cte3.c.segment_start)).label('duration')
        )
        .group_by(cte3.c.segment_id, cte3.c.is_paused)
        .order_by(cte3.c.segment_id)
    )

    result = await session.execute(final_query)
    segments = result.all()

    # Convert to list of dictionaries for easier processing
    return [
        {
            'segment_id': seg.segment_id,
            'is_paused': seg.is_paused,
            'segment_distance': seg.segment_distance or 0.0,
            'duration': seg.duration.total_seconds() if seg.duration else 0.0
        }
        for seg in segments
    ]


async def get_max_speed_for_track(
        session: AsyncSession,
        track_id: int,
        user_id: int
) -> float:
    """Get the maximum speed for a specific track.

    Args:
        session: Async database session
        track_id: ID of the track to query
        user_id: ID of the user requesting the data (for authorization)

    Returns:
        Maximum speed in meters per second (float)

    Raises:
        SessionAccessError: If user doesn't have access to the track
    """
    if not await can_access_track(session, user_id, track_id):
        raise SessionAccessError("User has no access to this track session")

    # Query to get the maximum speed from locations for this track
    query = select(
        func.max(Location.speed_mps)
    ).where(
        Location.track_id == track_id
    )

    result = await session.execute(query)
    max_speed = result.scalar()

    return max_speed if max_speed is not None else 0.0

async def calculate_track_statistics(
        session: AsyncSession,
        track_id: int,
        user_id: int,
) -> dict:
    """Calculate and return session statistics including:
    - distance_m_total (excluding paused points)
    - speed_mps_max (excluding paused points)
    - speed_mps_average (excluding paused points)
    - duration_s_active (excluding paused points)
    - duration_s_total (including all points)
    """
    if not await can_access_track(session, user_id, track_id):
        raise SessionAccessError("User has no access to this track session")

    # First ensure all speeds are calculated
    # await calculate_speeds_for_track(session, track_id, user_id)

    segments_statistics = await get_segments_statistics(session, track_id, user_id)
    logger.debug(f"Segment statistics: {segments_statistics}")

    # Initialize statistics
    stats = {
        'distance_m_total': 0.0,
        'speed_mps_max': 0.0,
        'speed_mps_average': 0.0,
        'duration_s_active': 0.0,
        'duration_s_total': 0.0
    }

    for segment in segments_statistics:
        stats['duration_s_total'] += segment.get("segment_duration", 0)
        if not segment.get("is_paused", False):
            stats['distance_m_total'] += segment.get("segment_distance", 0)
            stats['duration_s_active'] += segment.get("segment_duration", 0)

    stats['speed_mps_average'] = stats['distance_m_total'] / stats['duration_s_active'] if stats['duration_s_active'] else 0.0
    stats['speed_mps_max'] = await get_max_speed_for_track(session, track_id, user_id)

    # Update the Track record with these statistics
    await session.execute(
        update(Track)
        .where(Track.track_id == track_id)
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
