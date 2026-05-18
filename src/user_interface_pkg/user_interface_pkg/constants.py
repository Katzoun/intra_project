from dataclasses import dataclass
from typing import Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel
from core_pkg.dbmodels.schemas import Permissions, PERM_META, PermissionsKeys

ALL_ROLES_OPTION = 'All Roles'

CALL_TIMEOUT_SEC = 10.0

@dataclass(frozen=True)
class NavSections:
    MAIN: str = 'main'
    ADMIN: str = 'admin'
    SYSTEM: str = 'system'

class PageInfo(BaseModel):
    route: str
    name: str # name to be displayed in the UI
    icon: str # icon name for the UI
    page: str # unique page identifier
    section: Optional[str] = "main"  # optional, for grouping/navigation
    permission: Optional[str] = None  # optional, permission required to access


# Define page info constants
LOGIN_PAGE = PageInfo(route='/login', name='Login', icon='login', page='login', permission=None)
DASHBOARD_PAGE = PageInfo(route='/', name='Dashboard', icon='dashboard', page='dashboard', section=NavSections.MAIN, permission=None)
SETTINGS_PAGE = PageInfo(route='/settings', name='Settings', icon='settings', page='settings', section=NavSections.MAIN, permission=None)
SYSTEM_CONTROL_PAGE = PageInfo(route='/system_control', name='System Control', icon='precision_manufacturing', page='system_control', section=NavSections.MAIN, permission= PermissionsKeys.ALLOW_SYSTEM_CONTROL)
OPERATIONS_PAGE = PageInfo(route='/operations', name='Operations', icon='build_circle', page='operations', section=NavSections.MAIN, permission= PermissionsKeys.ALLOW_MANAGE_OPERATIONS)
CONFIGURATION_PAGE = PageInfo(route='/config', name='Configuration', icon='tune', page='configuration', section=NavSections.ADMIN, permission= PermissionsKeys.ALLOW_SYSTEM_CONFIG)
ROBOT_PAGE = PageInfo(route='/robot_preview', name='Robot', icon='adjust', page='robot', section=NavSections.MAIN, permission= PermissionsKeys.ALLOW_ROBOT_PREVIEW)
TOOL_CONTROLLER_PAGE = PageInfo(route='/tool_control', name='Tool Control', icon='build', page='tool_control', section=NavSections.MAIN, permission= PermissionsKeys.ALLOW_SYSTEM_CONTROL)
USER_MANAGEMENT_PAGE = PageInfo(route='/users', name='User Management', icon='group', page='users', section=NavSections.ADMIN, permission= PermissionsKeys.ALLOW_USER_MANAGEMENT)


@dataclass(frozen=True)
class StorageConstants:
    # User session storage keys
    AUTH_TOKEN: str = 'auth_token'
    LOGIN: str = 'login'
    ACCESSOR_ID: str = 'accessor_id'
    ROLE_ID: str = 'role_id'
    ROLE: str = 'role'
    REFERRER_PATH: str = 'referrer_path'
    LAST_ACTIVE: str = 'last_active'


@dataclass(frozen=True)
class NavItem:
    name: str
    icon: str
    route: str
    page: str
    permission: Optional[str]
    section: str

@dataclass(frozen=True)
class NavSections:
    MAIN: str = 'main'
    ADMIN: str = 'admin'
    SYSTEM: str = 'system'

NAV_ITEMS = [
    DASHBOARD_PAGE,
    SETTINGS_PAGE,
    SYSTEM_CONTROL_PAGE,
    OPERATIONS_PAGE,
    TOOL_CONTROLLER_PAGE,
    CONFIGURATION_PAGE,
    ROBOT_PAGE,
    USER_MANAGEMENT_PAGE,
] 

