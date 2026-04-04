from sqlalchemy import Column, Integer, String, Float, DateTime
from sqlalchemy.sql import func
from .database import Base
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

# SQLAlchemy table
class PaymentTable(Base):
    __tablename__ = "payments"

    id             = Column(Integer, primary_key=True, index=True)
    username       = Column(String, nullable=False, index=True)
    order_id       = Column(Integer, nullable=False)
    amount         = Column(Float, nullable=False)
    payment_method = Column(String, nullable=False)
    status         = Column(String, default="completed")
    created_at     = Column(DateTime(timezone=True), server_default=func.now())

# Pydantic schemas
class PaymentCreate(BaseModel):
    order_id: int
    payment_method: str

class PaymentResponse(BaseModel):
    id: int
    username: str
    order_id: int
    amount: float
    payment_method: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True