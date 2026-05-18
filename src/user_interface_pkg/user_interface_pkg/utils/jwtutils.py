import jwt
from core_pkg.settings import JWT_SECRET, INACTIVITY_TIMEOUT_SECONDS
import time
from typing import Optional
from core_pkg.dbmodels.schemas import AccessorDTO

from nicegui import app, ui
from user_interface_pkg.constants import StorageConstants
from core_pkg.dbservices_async.accessor_async import get_accessor_by_id_async
from user_interface_pkg.constants import LOGIN_PAGE




JWT_ALG = 'HS256'


def create_jwt(username: str) -> str:
    """Creates a JWT for the given user (no expiry — session lifetime is
    governed by the inactivity timeout stored in *last_active*)."""
    payload = {
        'sub': username,
        'iat': int(time.time()),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)


def verify_jwt(token: Optional[str]) -> bool:
    """Verifies the JWT signature (ignores expiry — use inactivity timeout)."""
    if not token:
        return False
    try:
        jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG],
                   options={'verify_exp': False})
        return True
    except Exception:
        return False


def get_username_from_token(token: Optional[str]) -> Optional[str]:
    """Extracts the username from the token."""
    if not token:
        return None
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG],
                             options={'verify_exp': False})
        return payload.get('sub')
    except Exception:
        return None



def is_session_active() -> bool:
    """
    Return True if a valid token exists AND the user was active
    within the last INACTIVITY_TIMEOUT_SECONDS.
    Safe to call from middleware / on_connect (catches RuntimeError).
    """
    token = app.storage.user.get(StorageConstants.AUTH_TOKEN, None)
    if not verify_jwt(token):
        return False

    last_active = app.storage.user.get(StorageConstants.LAST_ACTIVE, None)
    if last_active is None:
        return False

    return (time.time() - last_active) < INACTIVITY_TIMEOUT_SECONDS


def touch_session() -> None:
    """Update the last-activity timestamp to *now*."""
    app.storage.user[StorageConstants.LAST_ACTIVE] = time.time()


def clear_session_and_redirect() -> None:
    """Clear stale user session data and redirect to login page."""
    app.storage.user.clear()
    ui.navigate.to(LOGIN_PAGE.route)


async def get_valid_accessor() -> Optional['AccessorDTO']:
    """
    Validate the current session and return the AccessorDTO.

    Checks that:
    1. A valid JWT token exists in session storage
    2. The user has been active within INACTIVITY_TIMEOUT_SECONDS
    3. The accessor_id in storage maps to a real user in the DB

    On success the *last_active* timestamp is refreshed (sliding window).
    If validation fails, clears session and redirects to login.
    Returns None only when a redirect has been triggered (caller should return early).
    """
    # 1. Token signature + inactivity check
    if not is_session_active():
        clear_session_and_redirect()
        return None

    # 2. Load accessor from DB
    accessor_id = app.storage.user.get(StorageConstants.ACCESSOR_ID, None)
    if accessor_id is None:
        clear_session_and_redirect()
        return None

    try:
        accessor_dto = await get_accessor_by_id_async(accessor_id)
    except Exception:
        accessor_dto = None

    if accessor_dto is None:
        clear_session_and_redirect()
        return None

    # 3. Refresh last-activity (sliding window)
    touch_session()

    return accessor_dto
