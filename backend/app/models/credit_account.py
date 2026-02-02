from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.sql import func

from app.core.database import Base


class CreditAccount(Base):
    __tablename__ = "credit_accounts"

    user_id = Column(String, primary_key=True, index=True)
    balance = Column(Integer, default=0)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

