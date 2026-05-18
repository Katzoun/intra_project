"""
Repository for authentication and authorization operations
"""
from typing import Optional, List
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_

from core_pkg.dbrepositories.base_repository import TimestampedRepository
from core_pkg.dbmodels.tables import Accessors, Roles

class RoleRepository(TimestampedRepository[Roles]):
    """Repository for Role management"""
    
    def __init__(self, db: Session):
        super().__init__(db, Roles)
    
    def get_by_name(self, name: str) -> Optional[Roles]:
        """Get role by name"""
        return self.db.query(Roles).filter(Roles.name.ilike(name)).first()
    
    def get_roles_with_users(self) -> List[Roles]:
        """Get all roles with their users loaded"""
        return (
            self.db.query(Roles)
            .options(joinedload(Roles.accessors))
            .all()
        )
    def create_role(self, role: Roles) -> Roles:
        """Create a new role"""
        self.db.add(role)
        self.db.flush()
        self.db.refresh(role)
        return role
    
    def delete_role(self, role_id: int) -> None:
        """Delete role by ID"""
        self.db.query(Roles).filter(Roles.role_id == role_id).delete()
        self.db.flush()

    def name_exists(self, name: str, exclude_id: Optional[int] = None) -> bool:
        """Check if role name already exists"""
        query = self.db.query(Roles).filter(Roles.name.ilike(name))
        if exclude_id:
            query = query.filter(Roles.role_id != exclude_id)
        return query.first() is not None

class AccessorRepository(TimestampedRepository[Accessors]):
    """Repository for Accessor (user) management"""
    
    def __init__(self, db: Session):
        super().__init__(db, Accessors)

    def get_by_login(self, login: str) -> Optional[Accessors]:
        """Get user by login"""
        return (
            self.db.query(Accessors)
            .options(joinedload(Accessors.role))  # Eager load role
            .filter(Accessors.login.ilike(login))
            .first()
        )
    
    def change_password(self, accessor_id: int, new_password_hash: str) -> None:
        """Change password hash for accessors"""
        self.db.query(Accessors).filter(
            Accessors.accessor_id == accessor_id
        ).update({Accessors.password_hash: new_password_hash})
        self.db.flush()
    
    def get_by_role(self, role_name: str) -> List[Accessors]:
        """Get all accessors with specific role"""
        return (
            self.db.query(Accessors)
            .join(Roles)
            .filter(Roles.name.ilike(role_name))
            .options(joinedload(Accessors.role))
            .all()
        )
    
    def get_by_role_id(self, role_id: int) -> List[Accessors]:
        """Get all accessors with specific role ID"""
        return (
            self.db.query(Accessors)
            .filter(Accessors.role_id == role_id)
            .options(joinedload(Accessors.role))
            .all()
        )
    
    def search_users(self, search_term: str) -> List[Accessors]:
        """Search accessors by name or login"""
        return (
            self.db.query(Accessors)
            .options(joinedload(Accessors.role))
            .filter(
                or_(
                    Accessors.name.ilike(f"%{search_term}%"),
                    Accessors.login.ilike(f"%{search_term}%"),
                    Accessors.description.ilike(f"%{search_term}%")
                )
            )
            .all()
        )
    
    def get_by_role_id_with_search(self, role_id: int, search_term: str) -> List[Accessors]:
        """Get accessors by role ID and search term"""
        return (
            self.db.query(Accessors)
            .filter(
                and_(
                    Accessors.role_id == role_id,
                    or_(
                        Accessors.name.ilike(f"%{search_term}%"),
                        Accessors.login.ilike(f"%{search_term}%"),
                        Accessors.description.ilike(f"%{search_term}%")
                    )
                )
            )
            .options(joinedload(Accessors.role))
            .all()
        )
    
    def login_exists(self, login: str, exclude_id: Optional[int] = None) -> bool:
        """Check if login already exists"""
        query = self.db.query(Accessors).filter(Accessors.login.ilike(login))
        if exclude_id:
            query = query.filter(Accessors.accessor_id != exclude_id)
        return query.first() is not None
    
    def create_accessor(self, accessor: Accessors) -> Accessors:
        """Create a new accessor"""
        self.db.add(accessor)
        self.db.flush()
        self.db.refresh(accessor)
        return accessor
    
