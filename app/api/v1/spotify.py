from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone, timedelta
from uuid import UUID
import secrets
from app.api.deps import get_current_user
from app.core.database import get_db
from app.crud import spotify as crud_spotify
from app.schemas import spotify as schemas_spotify
from app.services import spotify_auth, spotify_api

router = APIRouter()


@router.get("/authorize")
async def authorize_spotify(
    current_user: dict = Depends(get_current_user),
):
    """
    Start Spotify OAuth flow.
    Returns authorization URL for user to visit.
    """
    # Generate state for CSRF protection
    state = secrets.token_urlsafe(32)
    # In production, you might want to store this state temporarily
    # and verify it in the callback
    
    authorize_url = spotify_auth.generate_authorize_url(state)
    return {"authorize_url": authorize_url, "state": state}


@router.get("/callback")
async def spotify_callback(
    code: str = Query(...),
    state: str = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Handle Spotify OAuth callback.
    Exchanges code for tokens and stores connection.
    """
    try:
        # Exchange code for tokens
        token_data = await spotify_auth.exchange_code_for_tokens(code)
        
        # Get Spotify user ID
        spotify_user_id = await spotify_auth.get_spotify_user_id(
            token_data["access_token"]
        )
        
        # Calculate expiration time
        expires_at = datetime.now(timezone.utc) + timedelta(
            seconds=token_data.get("expires_in", 3600)
        )
        
        user_id = UUID(current_user["id"])
        
        # Check if connection already exists
        existing = await crud_spotify.get_spotify_connection(db, user_id)
        
        if existing:
            # Update existing connection
            connection = await crud_spotify.update_spotify_connection(
                db,
                existing,
                token_data["access_token"],
                token_data.get("refresh_token"),
                expires_at,
            )
        else:
            # Create new connection
            connection = await crud_spotify.create_spotify_connection(
                db,
                user_id,
                spotify_user_id,
                token_data["access_token"],
                token_data["refresh_token"],
                expires_at,
            )
        
        return {
            "message": "Spotify connected successfully",
            "spotify_user_id": spotify_user_id,
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to connect Spotify: {str(e)}",
        )


@router.get("/status", response_model=schemas_spotify.SpotifyStatusResponse)
async def get_spotify_status(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Check if user has connected Spotify."""
    user_id = UUID(current_user["id"])
    connection = await crud_spotify.get_spotify_connection(db, user_id)
    
    if connection:
        return schemas_spotify.SpotifyStatusResponse(
            connected=True,
            spotify_user_id=connection.spotify_user_id,
        )
    return schemas_spotify.SpotifyStatusResponse(connected=False)


@router.post("/disconnect")
async def disconnect_spotify(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Remove Spotify connection for user."""
    user_id = UUID(current_user["id"])
    deleted = await crud_spotify.delete_spotify_connection(db, user_id)
    
    if deleted:
        return {"message": "Spotify disconnected successfully"}
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="No Spotify connection found",
    )


@router.get("/playlists", response_model=schemas_spotify.SpotifyPlaylistsResponse)
async def get_playlists(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(50, ge=1, le=50),
    offset: int = Query(0, ge=0),
):
    """Get user's Spotify playlists."""
    user_id = UUID(current_user["id"])
    
    try:
        # Get valid access token
        access_token = await spotify_api.get_valid_spotify_token(user_id, db)
        
        # Fetch playlists from Spotify
        playlists_data = await spotify_api.get_user_playlists(
            access_token, limit=limit, offset=offset
        )
        
        # Transform to response format
        playlists = []
        for item in playlists_data.get("items", []):
            images = item.get("images", [])
            image_url = images[0]["url"] if images else None
            
            playlists.append(
                schemas_spotify.SpotifyPlaylist(
                    id=item["id"],
                    name=item["name"],
                    description=item.get("description"),
                    tracks_count=item.get("tracks", {}).get("total"),
                    image_url=image_url,
                )
            )
        
        return schemas_spotify.SpotifyPlaylistsResponse(
            playlists=playlists,
            total=playlists_data.get("total", 0),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch playlists: {str(e)}",
        )
