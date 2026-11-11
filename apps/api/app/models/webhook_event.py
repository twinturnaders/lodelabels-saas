from sqlalchemy import Column, String, DateTime, JSON, Boolean
from sqlalchemy.sql import func

from app.db import Base


class WebhookEvent(Base):
    __tablename__ = "webhook_events"

    id = Column(String, primary_key=True, index=True)
    provider = Column(String, nullable=False, default="whatnot")
    webhook_id = Column(String, unique=True, nullable=False, index=True) # DEDUPE!
    topic = Column(String, nullable=False) # e.g., "orders.created"
    seller_id = Column(String, nullable=True)
    payload = Column(JSON, nullable=False)
    processed = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())