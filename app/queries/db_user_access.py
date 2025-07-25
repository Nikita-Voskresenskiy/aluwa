from sqlalchemy.ext.asyncio import AsyncSession
from models import User, Track
from sqlalchemy.future import select

async def get_user_id_by_telegram_id(
    session: AsyncSession,
    telegram_id: int
) -> int:
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
    return user_id

async def can_access_track(
    db: AsyncSession,
    user_id: int,
    track_id: int
) -> bool:
    """Check if user owns the track session"""
    result = await db.execute(
        select(Track)
        .where(Track.user_id == user_id)
        .where(Track.track_id == track_id)
    )
    return len(result.scalars().all()) > 0