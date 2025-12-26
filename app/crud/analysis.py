from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import List, Optional
from uuid import UUID
from app.models.analysis import PlaylistAnalysis


async def create_playlist_analysis(
    db: AsyncSession,
    user_id: UUID,
    playlist_id: str,
    playlist_name: str,
    mood_results: dict,
) -> PlaylistAnalysis:
    """Create a new playlist analysis."""
    analysis = PlaylistAnalysis(
        user_id=user_id,
        playlist_id=playlist_id,
        playlist_name=playlist_name,
        mood_results=mood_results,
    )
    db.add(analysis)
    await db.commit()
    await db.refresh(analysis)
    return analysis


async def get_playlist_analysis(
    db: AsyncSession, analysis_id: UUID
) -> Optional[PlaylistAnalysis]:
    """Get a specific playlist analysis by ID."""
    stmt = select(PlaylistAnalysis).where(PlaylistAnalysis.id == analysis_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_user_analyses(
    db: AsyncSession, user_id: UUID, limit: int = 50, offset: int = 0
) -> List[PlaylistAnalysis]:
    """Get all analyses for a user, ordered by created_at DESC."""
    stmt = (
        select(PlaylistAnalysis)
        .where(PlaylistAnalysis.user_id == user_id)
        .order_by(desc(PlaylistAnalysis.created_at))
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    return result.scalars().all()
