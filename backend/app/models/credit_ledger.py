from sqlalchemy import JSON, Column, DateTime, Integer, String
from sqlalchemy.sql import func

from app.core.database import Base


class CreditLedger(Base):
    __tablename__ = "credit_ledger"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True)
    lot_id = Column(String, index=True, nullable=True)
    event_type = Column(String, index=True)
    delta = Column(Integer)
    source = Column(String, index=True)
    job_id = Column(Integer, index=True, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=True)
    event_metadata = Column("metadata", JSON, nullable=True)
