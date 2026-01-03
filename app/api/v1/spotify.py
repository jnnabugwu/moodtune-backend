from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from datetime import datetime, timedelta, timezone
from uuid import UUID
import secrets
from urllib.parse import urlencode
from app.api.deps import get_current_user
from app.core.config import settings
from app.crud import spotify as crud_spotify
from app.crud import spotify_state as crud_spotify_state
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
    try:
        # Generate and persist state (10 minute TTL)
        state = secrets.token_urlsafe(32)
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
        await crud_spotify_state.create_state(state, UUID(current_user["id"]), expires_at)

        authorize_url = spotify_auth.generate_authorize_url(state)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )
    return {"authorize_url": authorize_url, "state": state}


@router.get("/callback")
async def spotify_callback(
    code: str = Query(...),
    state: str = Query(None),
):
    """
    Handle Spotify OAuth callback.
    Exchanges code for tokens and stores connection.
    """
    try:
        # Resolve user from state (public endpoint)
        if not state:
            raise ValueError("Missing state")
        state_record = await crud_spotify_state.get_state(state)
        if not state_record:
            raise ValueError("Invalid or expired state")
        user_id = UUID(state_record["user_id"])
        # Single-use: delete state
        await crud_spotify_state.delete_state(state)

        token_data = await spotify_auth.exchange_code_for_tokens(code)
        spotify_user_id = await spotify_auth.get_spotify_user_id(
            token_data["access_token"]
        )
        expires_at = datetime.now(timezone.utc) + timedelta(
            seconds=token_data.get("expires_in", 3600)
        )

        refresh_token = token_data.get("refresh_token")
        existing = await crud_spotify.get_spotify_connection(user_id)

        if existing:
            connection = await crud_spotify.update_spotify_connection(
                existing,
                token_data["access_token"],
                refresh_token,
                expires_at,
            )
            refresh_token = connection.get("refresh_token", refresh_token)
        else:
            if not refresh_token:
                raise ValueError("Missing refresh token from Spotify response")
            await crud_spotify.create_spotify_connection(
                user_id,
                spotify_user_id,
                token_data["access_token"],
                refresh_token,
                expires_at,
            )

        if settings.SPOTIFY_APP_REDIRECT_URI:
            success_query = urlencode(
                {"status": "success", "spotify_user_id": spotify_user_id}
            )
            redirect_url = f"{settings.SPOTIFY_APP_REDIRECT_URI}?{success_query}"
            return RedirectResponse(url=redirect_url)

        return {
            "message": "Spotify connected successfully",
            "spotify_user_id": spotify_user_id,
        }
    except Exception as e:
        if settings.SPOTIFY_APP_REDIRECT_URI:
            error_query = urlencode(
                {"status": "error", "message": str(e)[:200]}
            )
            redirect_url = f"{settings.SPOTIFY_APP_REDIRECT_URI}?{error_query}"
            return RedirectResponse(url=redirect_url, status_code=status.HTTP_400_BAD_REQUEST)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to connect Spotify: {str(e)}",
        )


@router.get("/status", response_model=schemas_spotify.SpotifyStatusResponse)
async def get_spotify_status(
    current_user: dict = Depends(get_current_user),
):
    """Check if user has connected Spotify."""
    user_id = UUID(current_user["id"])
    connection = await crud_spotify.get_spotify_connection(user_id)
    
    if connection:
        return schemas_spotify.SpotifyStatusResponse(
            connected=True,
            spotify_user_id=connection.get("spotify_user_id"),
        )
    return schemas_spotify.SpotifyStatusResponse(connected=False)


@router.get("/profile", response_model=schemas_spotify.SpotifyProfileResponse)
async def get_spotify_profile(
    current_user: dict = Depends(get_current_user),
):
    """Fetch the connected Spotify user profile."""
    user_id = UUID(current_user["id"])
    try:
        access_token = await spotify_api.get_valid_spotify_token(user_id)
        profile_data = await spotify_api.get_user_profile(access_token)

        images = profile_data.get("images") or []
        image_url = images[0]["url"] if images else None
        followers = (profile_data.get("followers") or {}).get("total")

        return schemas_spotify.SpotifyProfileResponse(
            profile=schemas_spotify.SpotifyProfile(
                id=profile_data.get("id", ""),
                display_name=profile_data.get("display_name"),
                email=profile_data.get("email"),
                image_url=image_url,
                followers=followers,
                product=profile_data.get("product"),
            )
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch Spotify profile: {str(e)}",
        )


@router.post("/disconnect")
async def disconnect_spotify(
    current_user: dict = Depends(get_current_user),
):
    """Remove Spotify connection for user."""
    user_id = UUID(current_user["id"])
    deleted = await crud_spotify.delete_spotify_connection_by_user(user_id)
    
    if deleted:
        return {"message": "Spotify disconnected successfully"}
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="No Spotify connection found",
    )


@router.get("/playlists", response_model=schemas_spotify.SpotifyPlaylistsResponse)
async def get_playlists(
    current_user: dict = Depends(get_current_user),
    limit: int = Query(50, ge=1, le=50),
    offset: int = Query(0, ge=0),
):
    """Get user's Spotify playlists."""
    user_id = UUID(current_user["id"])
    
    try:
        # Get valid access token
        access_token = await spotify_api.get_valid_spotify_token(user_id)
        
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
