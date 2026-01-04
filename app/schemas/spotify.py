from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from uuid import UUID


class SpotifyConnectionBase(BaseModel):
    spotify_user_id: str


class SpotifyConnectionCreate(SpotifyConnectionBase):
    access_token: str
    refresh_token: str
    expires_at: datetime


class SpotifyConnectionResponse(SpotifyConnectionBase):
    id: UUID
    user_id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SpotifyStatusResponse(BaseModel):
    connected: bool
    spotify_user_id: Optional[str] = None


class SpotifyPlaylist(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    tracks_count: Optional[int] = None
    image_url: Optional[str] = None


class SpotifyPlaylistsResponse(BaseModel):
    playlists: list[SpotifyPlaylist]
    total: int


class SpotifyProfile(BaseModel):
    id: str
    display_name: Optional[str] = None
    email: Optional[str] = None
    image_url: Optional[str] = None
    followers: Optional[int] = None
    playlists_count: Optional[int] = None
    product: Optional[str] = None


class SpotifyProfileResponse(BaseModel):
    profile: SpotifyProfile
