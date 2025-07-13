from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base


class Analysis(Base):
    __tablename__ = "analyses"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    track_id = Column(String, nullable=False)
    track_name = Column(String, nullable=False)
    artist_name = Column(String, nullable=False)
    mood_score = Column(Float, nullable=False)
    energy_score = Column(Float, nullable=False)
    valence_score = Column(Float, nullable=False)
    danceability = Column(Float, nullable=False)
    tempo = Column(Float, nullable=False)
    analysis_data = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="analyses") 