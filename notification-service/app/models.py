from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.sql import func
from .database import Base
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

#  SQLAlchemy table **
class NotificationTable(Base):
    __tablename__ = "notifications"

    id         = Column(Integer, primary_key=True, index=True)
    username   = Column(String, nullable=False, index=True)
    message    = Column(String, nullable=False)
    type       = Column(String, nullable=False)
    is_read    = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

#  Pydantic schemas 

# Used internally by Payment Service only — not exposed to users
class NotificationInternal(BaseModel):
    username: str
    message: str
    type: str

class NotificationResponse(BaseModel):
    id: int
    username: str
    message: str
    type: str
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True