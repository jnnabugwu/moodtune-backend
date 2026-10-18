"""Delete a user's account and the data tied to it (issue #12).

Order matters:

1. The user's Spotify connection (stored Spotify tokens). Deleted explicitly
   because the live ``spotify_connections`` FK behaviour is unverified; see
   ``db/spotify_connections.sql``.
2. The Supabase auth user, through the service-role admin API. That cascades
   ``song_analyses``, ``playlist_analyses`` and ``spotify_oauth_states`` and
   sets ``mood_observations.user_id`` to NULL (see ``db/``).

Both steps are idempotent, so a retry after a partial failure (Spotify row
deleted, auth user not) is safe. Once the auth user is gone, the caller's
token no longer passes ``get_current_user``, so a retry after a *successful*
deletion gets 401, not 204. The not-found → 204 path covers the auth user
disappearing between token check and delete (e.g. two concurrent requests).

The service-role key bypasses RLS: only ever pass the authenticated caller's
id (``current_user["id"]``), never an id taken from the request.
"""

import asyncio
from typing import Union
from uuid import UUID

from gotrue.errors import AuthApiError

from app.core.supabase import get_supabase_service_client
from app.crud import spotify as crud_spotify


class AccountDeletionError(Exception):
    """A deletion step failed. ``step`` names it for logs and Sentry."""

    def __init__(self, step: str):
        super().__init__(f"Account deletion failed at step: {step}")
        self.step = step


def _is_user_not_found(error: Exception) -> bool:
    """
    True when the admin API says the auth user no longer exists. Only
    structured auth errors count; any other error is a failure.
    """
    if not isinstance(error, AuthApiError):
        return False
    return error.status == 404 or getattr(error, "code", None) == "user_not_found"


async def delete_account(user_id: Union[str, UUID]) -> None:
    """
    Delete the user's Spotify connection, then their Supabase auth user.

    Returns normally when the admin API reports the auth user already gone.

    Raises:
        AccountDeletionError: a step failed; the original error is chained
            as ``__cause__``.
    """
    user_id = str(user_id)

    try:
        await crud_spotify.delete_spotify_connection_by_user(user_id)
    except Exception as e:
        raise AccountDeletionError("spotify_connection") from e

    loop = asyncio.get_running_loop()

    def _delete_auth_user():
        client = get_supabase_service_client()
        client.auth.admin.delete_user(user_id)

    try:
        await loop.run_in_executor(None, _delete_auth_user)
    except Exception as e:
        if _is_user_not_found(e):
            return
        raise AccountDeletionError("auth_user") from e
