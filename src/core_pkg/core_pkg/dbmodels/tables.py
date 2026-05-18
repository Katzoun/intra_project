from sqlalchemy import String, Integer, ForeignKey, DateTime, BigInteger, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import CITEXT, ENUM, CHAR
from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy import inspect

from core_pkg.dbmodels.base import Base, TimestampMixin


class Roles(Base, TimestampMixin):
    """Maps "Roles" table from migration"""
    __tablename__ = "Roles"
    
    role_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(CITEXT, unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String)
    color: Mapped[str] = mapped_column(String, default='bg-grey text-white')

     # Permission columns
    allow_system_config: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default='false')
    allow_user_management: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default='false')
    allow_system_control: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default='false')
    allow_robot_preview: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default='false')
    allow_manage_operations: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default='false')
    
    # Relationships
    accessors: Mapped[List["Accessors"]] = relationship("Accessors", back_populates="role")
    
    # Excluded columns from permissions extraction
    _EXCLUDED_COLUMNS = {'role_id', 'name', 'description', 'created_at'}

    def get_permissions(self) -> Dict[str, Any]:
        """Dynamically extract all columns starting with 'allow_'."""
        mapper = inspect(self.__class__)
        permissions = {}
        
        for column in mapper.columns:
            column_name = column.key
            
            # Skip excluded columns
            if column_name in self._EXCLUDED_COLUMNS:
                continue
            
            # Include permission-related columns
            if column_name.startswith('allow_'):
                permissions[column_name] = getattr(self, column_name)
        
        return permissions

class Accessors(Base, TimestampMixin):
    """Maps "Accessors" table from migration"""
    __tablename__ = "Accessors"

    accessor_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    login: Mapped[str] = mapped_column(CITEXT, unique=True, nullable=False, index=True)  # idx_accessor_login
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String)
    role_id: Mapped[int] = mapped_column(
        ForeignKey("Roles.role_id", ondelete="RESTRICT"), 
        nullable=False, 
    )
    active : Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default='true')
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    
    # Relationships
    role: Mapped["Roles"] = relationship("Roles", back_populates="accessors")

