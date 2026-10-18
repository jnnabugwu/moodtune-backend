import logging
from typing import Optional

import sentry_sdk
from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.security import HTTPAuthorizationCredentials

from app.api.deps import get_current_user, security_optional
from app.services import account_service

logger = logging.getLogger(__name__)

router = APIRouter()


async def require_bearer(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_optional),
) -> None:
    """
    401 (not FastAPI's default 403) when the Bearer token is missing, as the
    app's contract for this endpoint requires. Runs before get_current_user,
    which returns 401 for a token that is present but invalid.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )


@router.delete(
    "",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_bearer)],
)
async def delete_account(current_user: dict = Depends(get_current_user)):
    """
    Delete the signed-in user's account and the data tied to it.

    204 on success, and also when the auth user vanishes between the token
    check and the delete (e.g. a concurrent request). A retry after a
    successful deletion gets 401: the token's user no longer exists. 500 with
    a generic detail if a step fails; retrying after a 500 is safe.
    """
    # Only ever the caller's own id: the service-role client bypasses RLS.
    user_id = current_user["id"]
    try:
        await account_service.delete_account(user_id)
    except account_service.AccountDeletionError as e:
        # Never log or report the token or email here; the user id is enough.
        logger.error(
            "Account deletion failed at step %s for user %s", e.step, user_id
        )
        with sentry_sdk.new_scope() as scope:
            scope.set_tag("account_delete_step", e.step)
            sentry_sdk.capture_exception(e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not delete account",
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
