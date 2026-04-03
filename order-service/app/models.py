from sqlalchemy import Column, Integer, String, Float, DateTime
from sqlalchemy.sql import func
from .database import Base
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

#  SQLAlchemy table 
class OrderTable(Base):
    __tablename__ = "orders"

    id           = Column(Integer, primary_key=True, index=True)
    username     = Column(String, nullable=False, index=True)
    product_id   = Column(Integer, nullable=False)
    product_name = Column(String, nullable=False)
    quantity     = Column(Integer, nullable=False)
    unit_price   = Column(Float, nullable=False)
    total_price  = Column(Float, nullable=False)
    status       = Column(String, default="pending")
    created_at   = Column(DateTime(timezone=True), server_default=func.now())

# Pydantic schemas 
class OrderCreate(BaseModel):
    product_id: int
    quantity: int

class OrderResponse(BaseModel):
    id: int
    username: str
    product_id: int
    product_name: str
    quantity: int
    unit_price: float
    total_price: float
    status: str
    created_at: datetime

    class Config:
        from_attributes = True