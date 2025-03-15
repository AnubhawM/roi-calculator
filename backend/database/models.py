# database/models.py
from sqlalchemy import Column, Integer, String, DateTime, Boolean, JSON, ForeignKey
from sqlalchemy.sql import func
from . import Base

class User(Base):
    __tablename__ = "users"
    
    # Primary fields
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    name = Column(String)
    
    # Status and role fields
    is_active = Column(Boolean, default=True)
    role = Column(String, default="user")
    status = Column(String, default="active")
    
    # Tracking fields
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_login = Column(DateTime(timezone=True))
    last_active = Column(DateTime(timezone=True))
    login_count = Column(Integer, default=0)
    
    # Additional data
    preferences = Column(JSON, default={})
    user_metadata  = Column(JSON, default={})
    ip_address = Column(String)
    user_agent = Column(String)

