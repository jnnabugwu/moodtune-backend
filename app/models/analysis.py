from sqlalchemy import Column, String, Index, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from app.core.database import Base
import uuid


class PlaylistAnalysis(Base):
    __tablename__ = "playlist_analyses"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    # Note: user_id references auth.users(id) in Supabase
    playlist_id = Column(String, nullable=False)
    playlist_name = Column(String, nullable=False)
    mood_results = Column(JSONB, nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), index=True)

    # Create indexes as specified in schema
    __table_args__ = (
        Index('idx_analyses_user_id', 'user_id'),
        Index('idx_analyses_created_at', 'created_at', postgresql_ops={'created_at': 'DESC'}),
    ) 