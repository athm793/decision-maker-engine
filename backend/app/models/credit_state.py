from sqlalchemy import Column, Integer
from app.core.database import Base


class CreditState(Base):
    __tablename__ = "credit_state"

    id = Column(Integer, primary_key=True)
    balance = Column(Integer, default=0)

