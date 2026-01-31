from sqlalchemy import Column, Integer, String, DateTime, Enum, JSON
from sqlalchemy.sql import func
from app.core.database import Base
import enum

class JobStatus(str, enum.Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

from sqlalchemy.orm import relationship

class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, index=True)
    status = Column(Enum(JobStatus), default=JobStatus.QUEUED)
    total_companies = Column(Integer, default=0)
    processed_companies = Column(Integer, default=0)
    decision_makers_found = Column(Integer, default=0)
    
    # Store the column mappings used for this job
    column_mappings = Column(JSON)
    
    # Store the actual list of companies to process (simplified for now)
    # In a real app, this might be a separate table or stored in S3/File
    companies_data = Column(JSON)

    selected_platforms = Column(JSON)
    max_contacts_total = Column(Integer, default=50)
    max_contacts_per_company = Column(Integer, default=1)
    credits_spent = Column(Integer, default=0)
    stop_reason = Column(String)
    options = Column(JSON)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    decision_makers = relationship("DecisionMaker", back_populates="job")
