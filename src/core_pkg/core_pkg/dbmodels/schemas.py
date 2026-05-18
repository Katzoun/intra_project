from dataclasses import dataclass
from pydantic import BaseModel
from datetime import datetime
from typing import Optional, Dict
from core_pkg.dbmodels.tables import Accessors, Roles

@dataclass(frozen=True)
class PermissionsKeys:
    ALLOW_SYSTEM_CONFIG: str = 'allow_system_config'
    ALLOW_USER_MANAGEMENT: str = 'allow_user_management'
    ALLOW_SYSTEM_CONTROL: str = 'allow_system_control'
    ALLOW_ROBOT_PREVIEW: str = 'allow_robot_preview'
    ALLOW_MANAGE_OPERATIONS: str = 'allow_manage_operations'

class Permissions(BaseModel):
    allow_system_config: bool = False
    allow_user_management: bool = False
    allow_system_control: bool = False
    allow_robot_preview: bool = False
    allow_manage_operations: bool = False

@dataclass(frozen=True)
class PermMetaKeys:
    LABEL: str = "label"
    DESCRIPTION: str = "description"

PERM_META: Dict[str, dict] = {
        PermissionsKeys.ALLOW_SYSTEM_CONFIG: {
            'label': 'System configuration',
            'description': 'Allows changing system-wide configuration and settings.',
        },
        PermissionsKeys.ALLOW_USER_MANAGEMENT: {
            'label': 'User management',
            'description': 'Allows creating, editing and deactivating users.',
        },
        PermissionsKeys.ALLOW_SYSTEM_CONTROL: {
            'label': 'System control',
            'description': 'Allows starting, stopping and controlling system operations.',
        },
        PermissionsKeys.ALLOW_ROBOT_PREVIEW: {
            'label': 'Robot preview',
            'description': 'Allows previewing robot status.',
        },
        PermissionsKeys.ALLOW_MANAGE_OPERATIONS: {
            'label': 'Manage operations',
            'description': 'Allows managing operations.',
        },
    }


@dataclass(frozen=True)
class AccessorDTOkeys:
    ACCESSOR_ID: str = 'accessor_id'
    LOGIN: str = 'login'
    NAME: str = 'name'
    DESCRIPTION: str = 'description'
    ROLE_ID: str = 'role_id'
    ACTIVE : str = 'active'
    PASSWORD_HASH: str = 'password_hash'
    ROLE_NAME: str = 'role_name'
    ROLE_COLOR: str = 'role_color'
    CREATED_AT: str = 'created_at'
    PERMISSIONS: str = 'permissions'

class AccessorDTO(BaseModel):
    accessor_id: int
    login: str
    name: str
    description: Optional[str] = None
    role_id: int
    active: bool = True
    password_hash: str
    role_name: Optional[str] = None
    role_color: Optional[str] = None
    created_at: Optional[datetime] = None

    # permissions from role:
    permissions: Permissions = Permissions()

    class Config:
        from_attributes = True

def accessor_to_dto(accessor: Accessors) -> AccessorDTO:
    """Convert Accessors ORM model to AccessorDTO"""
    perms = Permissions(
        allow_system_config=accessor.role.allow_system_config,
        allow_user_management=accessor.role.allow_user_management,
        allow_system_control=accessor.role.allow_system_control,
        allow_robot_preview=accessor.role.allow_robot_preview,
        allow_manage_operations=accessor.role.allow_manage_operations,
    )

    dto = AccessorDTO.model_validate(accessor)
    dto.permissions = perms
    dto.role_name = accessor.role.name
    dto.role_color = accessor.role.color
    
    return dto

class RoleDTO(BaseModel):
    role_id: int
    name: str
    description: Optional[str] = None
    color: Optional[str] = None
    created_at: Optional[datetime] = None
    user_count : Optional[int] = None

    # permissions 
    permissions: Permissions = Permissions()

    class Config:
        from_attributes = True

def role_to_dto(role: Roles) -> RoleDTO:
    """Convert Roles ORM model to RoleDTO"""
    perms = Permissions(
        allow_system_config=role.allow_system_config,
        allow_user_management=role.allow_user_management,
        allow_system_control=role.allow_system_control,
        allow_robot_preview=role.allow_robot_preview,
        allow_manage_operations=role.allow_manage_operations,
    )
    user_count = len(role.accessors) if role.accessors else 0

    dto = RoleDTO.model_validate(role)
    dto.permissions = perms
    dto.user_count = user_count
    return dto
