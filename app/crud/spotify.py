from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
from datetime import datetime, timezone
from uuid import UUID
from app.models.spotify_connection import SpotifyConnection


async def get_spotify_connection(
    db: AsyncSession, user_id: UUID
) -> Optional[SpotifyConnection]:
    """Get Spotify connection for a user."""
    stmt = select(SpotifyConnection).where(SpotifyConnection.user_id == user_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def create_spotify_connection(
    db: AsyncSession,
    user_id: UUID,
    spotify_user_id: str,
    access_token: str,
    refresh_token: str,
    expires_at: datetime,
) -> SpotifyConnection:
    """Create a new Spotify connection."""
    connection = SpotifyConnection(
        user_id=user_id,
        spotify_user_id=spotify_user_id,
        access_token=access_token,
        refresh_token=refresh_token,
        expires_at=expires_at,
    )
    db.add(connection)
    await db.commit()
    await db.refresh(connection)
    return connection


async def update_spotify_connection(
    db: AsyncSession,
    connection: SpotifyConnection,
    access_token: str,
    refresh_token: Optional[str] = None,
    expires_at: Optional[datetime] = None,
) -> SpotifyConnection:
    """Update an existing Spotify connection."""
    connection.access_token = access_token
    if refresh_token:
        connection.refresh_token = refresh_token
    if expires_at:
        connection.expires_at = expires_at
    connection.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(connection)
    return connection


async def delete_spotify_connection(
    db: AsyncSession, user_id: UUID
) -> bool:
    """Delete Spotify connection for a user."""
    connection = await get_spotify_connection(db, user_id)
    if connection:
        await db.delete(connection)
        await db.commit()
        return True
    return False
