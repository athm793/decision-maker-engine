from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.sql import func

from app.core.database import Base


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True, unique=True)
    plan_key = Column(String, index=True)
    status = Column(String, index=True)
    current_period_end = Column(DateTime(timezone=True), nullable=True)
    provider = Column(String, index=True, nullable=True)
    provider_customer_id = Column(String, index=True, nullable=True)
    provider_subscription_id = Column(String, index=True, nullable=True)
    provider_order_id = Column(String, index=True, nullable=True)
    stripe_customer_id = Column(String, index=True, nullable=True)
    stripe_subscription_id = Column(String, index=True, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
