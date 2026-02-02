from sqlalchemy import Column, DateTime, Integer, JSON, String
from sqlalchemy.sql import func

from app.core.database import Base


class CouponCode(Base):
    __tablename__ = "coupon_codes"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String, unique=True, index=True)
    coupon_type = Column(String, index=True)
    active = Column(Integer, default=1)
    coupon_metadata = Column("metadata", JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class CouponAssignment(Base):
    __tablename__ = "coupon_assignments"

    id = Column(Integer, primary_key=True, index=True)
    coupon_code_id = Column(Integer, index=True)
    user_id = Column(String, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    redeemed_at = Column(DateTime(timezone=True), nullable=True)
