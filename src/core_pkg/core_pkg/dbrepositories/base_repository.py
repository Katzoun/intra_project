"""
Base repository with generic CRUD operations
"""
from typing import Generic, TypeVar, List, Optional, Dict, Any, Type
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, asc
from datetime import datetime

T = TypeVar('T')

class BaseRepository(Generic[T]):
    """Generic repository pattern for common CRUD operations"""
    
    def __init__(self, db: Session, model_class: Type[T]):
        self.db = db
        self.model_class = model_class
    
    # CREATE operations
    def create(self, obj_in: Dict[str, Any]) -> T:
        """Create new entity"""
        db_obj = self.model_class(**obj_in)
        self.db.add(db_obj)
        self.db.flush()
        return db_obj
    
    def create_bulk(self, objects_in: List[Dict[str, Any]]) -> List[T]:
        """Create multiple entities"""
        db_objects = [self.model_class(**obj_data) for obj_data in objects_in]
        self.db.add_all(db_objects)
        self.db.flush()
        return db_objects
    
    # READ operations
    def get_by_id(self, id: int) -> Optional[T]:
        """Get entity by primary key"""
        pk_column_name = self._get_pk_column()
        pk_column = getattr(self.model_class, pk_column_name)
        return self.db.query(self.model_class).filter(
            pk_column == id
        ).first()
    
    def get_pk_value(self, entity: T) -> Any:
        """Get primary key value from entity instance"""
        pk_column_name = self._get_pk_column()
        return getattr(entity, pk_column_name)
    
    def get_all(self, skip: int = 0, limit: int = 100) -> List[T]:
        """Get all entities with pagination"""
        if limit <= 0:
            limit = 100
        return (
            self.db.query(self.model_class)
            .offset(skip)
            .limit(limit)
            .all()
        )
    
    def count(self) -> int:
        """Count all entities"""
        return self.db.query(self.model_class).count()
    
    def exists(self, id: int) -> bool:
        """Check if entity exists"""
        return self.get_by_id(id) is not None
    
    # UPDATE operations
    def update(self, db_obj: T, obj_in: Dict[str, Any]) -> T:
        """Update existing entity"""
        for field, value in obj_in.items():
            if hasattr(db_obj, field):
                setattr(db_obj, field, value)
        self.db.flush()
        return db_obj
    
    def update_by_id(self, id: int, obj_in: Dict[str, Any]) -> Optional[T]:
        """Update entity by ID"""
        db_obj = self.get_by_id(id)
        if db_obj:
            return self.update(db_obj, obj_in)
        return None
    
    # DELETE operations
    def delete(self, db_obj: T) -> bool:
        """Delete entity"""
        self.db.delete(db_obj)
        self.db.flush()
        return True
    
    def delete_by_id(self, id: int) -> bool:
        """Delete entity by ID"""
        db_obj = self.get_by_id(id)
        if db_obj:
            return self.delete(db_obj)
        return False
    
    # SEARCH operations
    def filter_by(self, **filters) -> List[T]:
        """Filter entities by multiple criteria"""
        query = self.db.query(self.model_class)
        for field, value in filters.items():
            if hasattr(self.model_class, field):
                query = query.filter(getattr(self.model_class, field) == value)
        return query.all()
    
    def search(self, search_term: str, search_fields: List[str]) -> List[T]:
        """Search entities in specified fields"""
        if not search_term or not search_fields:
            return []
        
        query = self.db.query(self.model_class)
        conditions = []
        
        for field in search_fields:
            if hasattr(self.model_class, field):
                column = getattr(self.model_class, field)
                conditions.append(column.ilike(f"%{search_term}%"))
        
        if conditions:
            query = query.filter(or_(*conditions))
        
        return query.all()
    
    # HELPER methods
    def _get_pk_column(self) -> str:
        """Get primary key column name"""
        table = self.model_class.__table__
        primary_key = [col.name for col in table.columns if col.primary_key]
        if not primary_key:
            raise ValueError("No primary key found")
        return primary_key[0]

class TimestampedRepository(BaseRepository[T]):
    """Repository for models with timestamps"""
    
    def get_recent(self, limit: int = 10) -> List[T]:
        """Get most recently created entities"""
        return (
            self.db.query(self.model_class)
            .order_by(desc(self.model_class.created_at))
            .limit(limit)
            .all()
        )

    def get_created_between(self, start_date: datetime, end_date: datetime) -> List[T]:
        """Get entities created between dates"""

        return (
            self.db.query(self.model_class)
            .filter(
                and_(
                    self.model_class.created_at >= start_date,
                    self.model_class.created_at <= end_date
                )
            )
            .all()
        )
    