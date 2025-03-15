# database/schemas.py
from pydantic import BaseModel, EmailStr
from typing import Optional, Dict, Any
from datetime import datetime

class UserBase(BaseModel):
    email: EmailStr
    name: str
    
class UserCreate(UserBase):
    pass

class UserUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    preferences: Optional[Dict[str, Any]] = None
    status: Optional[str] = None

class UserInDB(UserBase):
    id: int
    is_active: bool
    role: str
    status: str
    created_at: datetime
    updated_at: Optional[datetime]
    last_login: Optional[datetime]
    last_active: Optional[datetime]
    login_count: int
    preferences: Dict[str, Any]
    user_metadata: Dict[str, Any]
    
    class Config:
        orm_mode = True

