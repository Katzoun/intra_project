"""
Base service with common functionality for all database services
"""

from contextlib import contextmanager
from core_pkg.settings import POSTGRES_DB_URL, DB_ECHO
from abc import ABC
from typing import Optional
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy import create_engine

# Database setup
engine = create_engine(
    POSTGRES_DB_URL, 
    echo=DB_ECHO,
    pool_pre_ping=True,  # Verify connections before use
)
# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Session management utilities
def get_db():
    """
    Database session dependency for FastAPI/dependency injection
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@contextmanager
def db_session(auto_commit: bool = False):
    """
    Context manager for non-web database operations
    Usage: 
        with db_session() as db:
            # database operations
            db.commit()  # Manual commit
        
        # or for simple operations:
        with db_session(auto_commit=True) as db:
            # database operations - auto commits on success
    """
    db = SessionLocal()
    try:
        yield db
        if auto_commit:
            db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

def create_session():
    """
    Simple session factory
    Remember to close manually: session.close()
    """
    return SessionLocal()



class BaseDBService(ABC):
    """Base class for all services"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def _validate_required_fields(self, data: dict, required_fields: list) -> None:
        """Validate that all required fields are present"""
        missing_fields = []
        for field in required_fields:
            if field not in data or data[field] is None or data[field] == "":
                missing_fields.append(field)
        
        if missing_fields:
            raise ValueError(f"Missing required fields: {', '.join(missing_fields)}")
    
    def _validate_field_length(self, value: str, field_name: str, min_length: int = 0, max_length: int = None) -> None:
        """Validate field length"""
        if len(value) < min_length:
            raise ValueError(f"{field_name} must be at least {min_length} characters long")
        
        if max_length and len(value) > max_length:
            raise ValueError(f"{field_name} must not exceed {max_length} characters")