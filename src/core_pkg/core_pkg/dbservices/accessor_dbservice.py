"""
Authentication and Authorization Service
Contains all business logic for accessor management and permissions
"""
import re
import bcrypt
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from core_pkg.dbservices import BaseDBService
from core_pkg.dbrepositories import AccessorRepository, RoleRepository
from core_pkg.dbmodels.tables import Accessors, Roles
from core_pkg.exceptions import ValidationError, NotFoundError, AuthenticationError
from core_pkg.systemconstants import DatabaseConstants
from core_pkg.dbmodels.schemas import Permissions, PERM_META

class AuthDBService(BaseDBService):
    """Service for authentication, authorization and other accessor business logic"""

    def __init__(self, db: Session):
        super().__init__(db)
        self.accessor_repo = AccessorRepository(db)
        self.role_repo = RoleRepository(db)

    def authenticate_accessor(self, login: str, password: str) -> Accessors:
        """Authenticate accessor by login and password. Returns the accessor on success."""
        
        print(f"Authenticating accessor: {login}")

        if not login or not password:
            raise ValidationError("Login and password are required")
        
        try:
            # Find accessor by login
            accessor = self.accessor_repo.get_by_login(login)
            if not accessor:
                raise AuthenticationError("Invalid credentials")
            
    
            if not verify_password(password, accessor.password_hash):
                raise AuthenticationError("Invalid credentials")
            if not accessor.role:
                raise AuthenticationError("Accessor has no role assigned")
            
            if not accessor.active:
                raise AuthenticationError("Accessor account is deactivated")

            return accessor
        
        except AuthenticationError:
            # Re-raise authentication errors (invalid credentials, etc.)
            raise
        
        except OperationalError as e:
            # Database connection error - re-raise for UI to handle
            raise 

    def change_accessor_password(self, accessor_id: int, current_password: str, new_password: str) -> bool:
        """Change password after verifying the current one. For self-service use."""
        accessor = self.accessor_repo.get_by_id(accessor_id)
        if not accessor:
            raise NotFoundError(f"Accessor with ID {accessor_id} not found")
        if not verify_password(current_password, accessor.password_hash):
            raise AuthenticationError("Current password is incorrect")
        

        validate_password_strength(new_password)
        

        if verify_password(new_password, accessor.password_hash):
            raise ValidationError("New password must be different from current password")
        
        self.accessor_repo.change_password(accessor_id, hash_password(new_password))
        return True
    
    def reset_accessor_password(self, accessor_id: int, new_password: str) -> bool:
        """Admin-initiated password reset (no current password needed)."""
        accessor = self.accessor_repo.get_by_id(accessor_id)
        if not accessor:
            raise NotFoundError(f"Accessor with ID {accessor_id} not found")
        

        validate_password_strength(new_password)
        
        self.accessor_repo.change_password(accessor_id, hash_password(new_password))
        return True
    
    def toggle_accessor_activation(self, accessor_id: int) -> bool:
        """Toggle accessor active/deactivated status. Returns new state."""
        accessor = self.accessor_repo.get_by_id(accessor_id)
        if not accessor:
            raise NotFoundError(f"Accessor with ID {accessor_id} not found")
        
        new_status = not accessor.active
        accessor.active = new_status
        self.db.flush()
        return new_status
    
    def update_accessor_role(self, accessor_id: int, new_role_id: int) -> None:
        """Assign a different role to an accessor."""
        accessor = self.accessor_repo.get_by_id(accessor_id)
        if not accessor:
            raise NotFoundError(f"Accessor with ID {accessor_id} not found")
        
        role = self.role_repo.get_by_id(new_role_id)
        if not role:
            raise NotFoundError(f"Role with ID {new_role_id} not found")
        
        accessor.role_id = new_role_id
        self.db.flush()

    def update_accessor_name_description(self, accessor_id: int, new_name: str, new_description: Optional[str]) -> None:
        """Update accessor's display name and description."""
        accessor = self.accessor_repo.get_by_id(accessor_id)
        if not accessor:
            raise NotFoundError(f"Accessor with ID {accessor_id} not found")

        validate_name_format(new_name)

        accessor.name = new_name
        if new_description is not None:
            validate_description_format(new_description)
            accessor.description = new_description
        self.db.flush()

    def update_accessor_login(self, accessor_id: int, new_login: str) -> None:
        """Change an accessor's login (must be unique)."""
        accessor = self.accessor_repo.get_by_id(accessor_id)
        if not accessor:
            raise NotFoundError(f"Accessor with ID {accessor_id} not found")
        

        if self.accessor_repo.login_exists(new_login):
            raise ValidationError(f"Login '{new_login}' already exists")

        # Validate login format
        validate_login_format(new_login)

        accessor.login = new_login
        self.db.flush()

    def create_new_accessor(self, login: str, name: str, description: Optional[str], active: bool, role_name: str, password: str) -> Accessors:
        """Create a new accessor with full validation."""

        if not login:
            raise ValidationError("Login is required")
        if not name:
            raise ValidationError("Name is required")
        if not password:
            raise ValidationError("Password is required")
        if not role_name:
            raise ValidationError("Role name is required")
        

        validate_login_format(login)
        validate_name_format(name)
        if description:
            validate_description_format(description)
        validate_password_strength(password)
        

        if self.accessor_repo.login_exists(login):
            raise ValidationError(f"Login '{login}' already exists")
        

        role = self.role_repo.get_by_name(role_name)
        if not role:
            raise NotFoundError(f"Role '{role_name}' not found")
        

        password_hash = hash_password(password)
        
        new_accessor = Accessors(
            login=login,
            name=name,
            description=description,
            active=active,
            role_id=role.role_id,
            password_hash=password_hash,
        )
        return self.accessor_repo.create_accessor(new_accessor)

    def update_role_permissions(self, role_id: int, new_permissions: Permissions) -> None:
        """Overwrite a role's permission flags."""
        role = self.role_repo.get_by_id(role_id)
        if not role:
            raise NotFoundError(f"Role with ID {role_id} not found")
        perm_keys = PERM_META.keys()

        for key in perm_keys:
        # Update permissions
            if hasattr(role,  key):
                setattr(role, key, getattr(new_permissions, key))

        self.db.flush()
    
    def create_role(self, name: str, permissions: Permissions, description: Optional[str]) -> Roles:
        """Create a new role with the given permissions."""
        if not name:
            raise ValidationError("Role name is required")
        # Validate role name format
        sanitized_name = validate_role_name_format(name)

        if description is not None:
            validate_description_format(description)
        if self.role_repo.name_exists(name):
            raise ValidationError(f"Role '{name}' already exists")
        
        role_data = Roles(
            name=sanitized_name,
            description=description,
            allow_system_config=permissions.allow_system_config,
            allow_user_management=permissions.allow_user_management,
            allow_system_control=permissions.allow_system_control,
            allow_robot_preview=permissions.allow_robot_preview,
            allow_manage_operations=permissions.allow_manage_operations,
        )
        
        return self.role_repo.create_role(role_data)
    
    def delete_role(self, role_id: int) -> None:
        """Delete a role (fails if any accessors are assigned to it)."""
        role = self.role_repo.get_by_id(role_id)
        if not role:
            raise NotFoundError(f"Role with ID {role_id} not found")
        
        accessor_count = len(role.accessors) if role.accessors else 0

        if accessor_count > 0:
            raise ValidationError(f"Cannot delete role '{role.name}' as it is assigned to existing accessors")
        self.role_repo.delete_role(role_id)
    

    def update_role_name_description(self, role_id: int, new_name: str, new_description: Optional[str]) -> None:
        """Rename a role and/or update its description."""
        role = self.role_repo.get_by_id(role_id)
        if not role:
            raise NotFoundError(f"Role with ID {role_id} not found")

        sanitized = validate_role_name_format(new_name)

        if role.name != sanitized and self.role_repo.name_exists(sanitized):
            raise ValidationError(f"Role name '{sanitized}' already exists")
        role.name = sanitized

        if new_description is not None:
            validate_description_format(new_description)
            role.description = new_description
        self.db.flush()
def hash_password(password: str) -> str:
    """Hash password using bcrypt"""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def verify_password(password: str, hashed: str) -> bool:
    """
    Verify password against hash

    Returns:
        True if match, False otherwise
    """
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def validate_password_strength(password: str) -> None:
    """
    Validate password strength according to security policy.
    
    Raises:
        ValidationError: If password doesn't meet requirements
    """
    # Length requirement
    if len(password) < DatabaseConstants.MIN_PASSWORD_LENGTH:
        raise ValidationError(f"Password must be at least {DatabaseConstants.MIN_PASSWORD_LENGTH} characters long")

    if len(password) > DatabaseConstants.MAX_PASSWORD_LENGTH:
        raise ValidationError(f"Password must be at most {DatabaseConstants.MAX_PASSWORD_LENGTH} characters long")

    # Uppercase letter requirement
    if not any(c.isupper() for c in password):
        raise ValidationError("Password must contain at least one uppercase letter")
    
    # Lowercase letter requirement
    if not any(c.islower() for c in password):
        raise ValidationError("Password must contain at least one lowercase letter")
    
    # Number requirement
    if not any(c.isdigit() for c in password):
        raise ValidationError("Password must contain at least one number")
    
def validate_login_format(login: str) -> None:
    """
    Validate login format according to business rules.
    
    Raises:
        ValidationError: If login doesn't meet requirements
    """
    if len(login) < DatabaseConstants.MIN_LOGIN_LENGTH or len(login) > DatabaseConstants.MAX_LOGIN_LENGTH:
        raise ValidationError(f"Login must be between {DatabaseConstants.MIN_LOGIN_LENGTH} and {DatabaseConstants.MAX_LOGIN_LENGTH} characters long")

    # Check format: only lowercase letters a-z and digits 0-9
    if not re.match(r'^[a-z0-9]+$', login):
        raise ValidationError(
        "Login can only contain lowercase letters (a-z) and digits (0-9). "
        "No spaces or special characters allowed"
        )
        
def validate_name_format(name: str) -> None:
    """
    Validate name format according to business rules.
    
    Raises:
        ValidationError: If name doesn't meet requirements
    """
    if len(name) < DatabaseConstants.MIN_NAME_LENGTH or len(name) > DatabaseConstants.MAX_NAME_LENGTH:
        raise ValidationError(f"Name must be between {DatabaseConstants.MIN_NAME_LENGTH} and {DatabaseConstants.MAX_NAME_LENGTH} characters long")

def validate_description_format(description: str) -> None:
    """
    Validate description format according to business rules.
    
    Raises:
        ValidationError: If description doesn't meet requirements
    """
    if len(description) > DatabaseConstants.MAX_DESCRIPTION_LENGTH:
        raise ValidationError(f"Description must be at most {DatabaseConstants.MAX_DESCRIPTION_LENGTH} characters long")
    
def validate_role_name_format(role_name: str) -> str:
    """
    Validate and sanitize role name.
    """
   
    if not role_name:
        raise ValidationError("Role name is required")

    sanitized = role_name.strip().lower()
    
    if len(sanitized) < DatabaseConstants.MIN_LOGIN_LENGTH or len(sanitized) > DatabaseConstants.MAX_LOGIN_LENGTH:
            raise ValidationError(f"Name must be between {DatabaseConstants.MIN_LOGIN_LENGTH} and {DatabaseConstants.MAX_LOGIN_LENGTH} characters long")

    # Check format: only lowercase letters a-z
    if not re.match(r'^[a-z]+$', sanitized):
        raise ValidationError(
            "Role name can only contain lowercase letters (a-z). "
            "No numbers, spaces, or special characters allowed"
        )
    
    return sanitized
