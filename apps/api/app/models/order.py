from sqlalchemy import Column, String, Integer, DateTime, JSON, ForeignKey
from sqlalchemy.sql import func
from app.db import Base

class Order(Base):
    __tablename__ = "orders"
    id = Column(String, primary_key=True, index=True)
    seller_id = Column(String, nullable=False, index=True)
    whatnot_order_id = Column(String, unique=True, nullable=False)
    buyer_username = Column(String, nullable=False)
    raw_payload = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

# ✅ RENAMED FROM Label TO SaleLabel
class SaleLabel(Base):
    __tablename__ = "labels"
    id = Column(String, primary_key=True, index=True)
    order_id = Column(String, ForeignKey("orders.id"), nullable=False)
    seller_id = Column(String, nullable=False, index=True)
    item_number = Column(Integer, nullable=False)
    buyer_number = Column(Integer, nullable=False)
    buyer_username = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    status = Column(String, default="generated")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class ShowCounter(Base):
    __tablename__ = "show_counters"
    seller_id = Column(String, primary_key=True, index=True)
    next_item_number = Column(Integer, default=1)
    next_buyer_number = Column(Integer, default=1)
    
class BuyerNumber(Base):
    __tablename__ = "buyer_numbers"
    seller_id = Column(String, primary_key=True, index=True)
    buyer_username = Column(String, primary_key=True)
    buyer_number = Column(Integer, nullable=False)