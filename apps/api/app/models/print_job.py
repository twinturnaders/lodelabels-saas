from sqlalchemy import Column, String, Integer, ForeignKey, DateTime
from sqlalchemy.sql import func
from app.db import Base

class PrintJob(Base):
    __tablename__ = "print_jobs"
    id = Column(String, primary_key=True, index=True)
    label_id = Column(String, ForeignKey("labels.id"), nullable=False)
    seller_id = Column(String, nullable=False, index=True)
    status = Column(String, default="queued") # queued, sent, printed, failed
    attempts = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())