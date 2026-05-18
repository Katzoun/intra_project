from sqlalchemy import  DateTime, func 
from sqlalchemy.orm import Mapped, mapped_column, DeclarativeBase
from sqlalchemy import MetaData
from datetime import datetime
from typing import Optional
from enum import Enum


_metadata = MetaData()



class Base(DeclarativeBase):
    metadata = _metadata

class TimestampMixin:
    """Mixin for created_at timestamp"""
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())

