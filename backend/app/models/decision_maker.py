from sqlalchemy import Column, Integer, String, ForeignKey, Float, Text
from sqlalchemy.orm import relationship
from app.core.database import Base

class DecisionMaker(Base):
    __tablename__ = "decision_makers"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id"))
    company_name = Column(String, index=True)
    company_type = Column(String)
    company_website = Column(String)
    name = Column(String)
    title = Column(String)
    platform = Column(String) # linkedin, google_maps, etc.
    profile_url = Column(String)
    confidence_score = Column(String) # HIGH, MEDIUM, LOW
    reasoning = Column(Text)
    
    job = relationship("Job", back_populates="decision_makers")
