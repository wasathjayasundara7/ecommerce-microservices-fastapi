from sqlalchemy import Column, Integer, String, Float, Boolean
from .database import Base
from pydantic import BaseModel
from typing import Optional

#SQLAlchemy table
class ProductTable(Base):
    __tablename__ = "products"

    id          = Column(Integer, primary_key=True, index=True)
    name        = Column(String, nullable=False, index=True)
    description = Column(String, nullable=True)
    price       = Column(Float, nullable=False)
    stock       = Column(Integer, default=0)
    category    = Column(String, nullable=True)
    is_active   = Column(Boolean, default=True)

#Pydantic schemas
class ProductCreate(BaseModel):
    name: str
    description: Optional[str] = None
    price: float
    stock: int = 0
    category: Optional[str] = None

class ProductUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    stock: Optional[int] = None
    category: Optional[str] = None
    is_active: Optional[bool] = None

class ProductResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    price: float
    stock: int
    category: Optional[str]
    is_active: bool

    class Config:
        from_attributes = True