from typing import Callable, Optional, Any
from functools import wraps
from fastapi.responses import RedirectResponse
from nicegui import ui, app
from user_interface_pkg.utils.jwtutils import get_valid_accessor
from user_interface_pkg.constants import DASHBOARD_PAGE, LOGIN_PAGE, StorageConstants
from core_pkg.dbmodels.schemas import AccessorDTO, PERM_META, PermMetaKeys




# Note: Authentication is already handled by auth_middleware in frontend_service.py
# These decorators ONLY check permissions, not authentication.

def require_permission(permission: str, redirect_to: str = DASHBOARD_PAGE.route):
    """
    Decorator to require specific permission for a page.
    Auth is already handled by middleware - this dec only checks permissions.
    
    Args:
        permission: Permission name (e.g., 'allow_system_control')
        redirect_to: Where to redirect if permission denied
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            # Validate session and get accessor (handles expired tokens)
            accessor = await get_valid_accessor()
            if accessor is None:
                return RedirectResponse(LOGIN_PAGE.route)
            
            if hasattr(accessor.permissions, permission):
                has_perm = getattr(accessor.permissions, permission)
            else:
                has_perm = False

            if not has_perm:
                print(f'Access denied: accessor {accessor.accessor_id} is missing permission {permission}')
                perm_name = PERM_META.get(permission).get(PermMetaKeys.LABEL)
                ui.notify(f'Access denied: {perm_name} permission required', color='negative')
                return RedirectResponse(redirect_to)

            return await func(*args, **kwargs)
        
        return wrapper
    return decorator