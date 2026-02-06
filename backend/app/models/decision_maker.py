from sqlalchemy import Column, Integer, String, ForeignKey, Float, Text, DateTime
from sqlalchemy.orm import relationship
from app.core.database import Base

class DecisionMaker(Base):
    __tablename__ = "decision_makers"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), index=True)
    company_name = Column(String, index=True)
    company_type = Column(String)
    company_city = Column(String)
    company_country = Column(String)
    company_website = Column(String)
    company_address = Column(Text)
    gmaps_rating = Column(Float)
    gmaps_reviews = Column(Integer)
    name = Column(String)
    title = Column(String)
    platform = Column(String) # linkedin, google_maps, etc.
    profile_url = Column(String)
    confidence_score = Column(String) # HIGH, MEDIUM, LOW
    reasoning = Column(Text)
    uploaded_company_data = Column(Text)
    llm_input = Column(Text)
    serper_queries = Column(Text)
    llm_output = Column(Text)
    llm_call_timestamp = Column(DateTime(timezone=True))
    serper_call_timestamp = Column(DateTime(timezone=True))
    emails_found = Column(Text)
    
    job = relationship("Job", back_populates="decision_makers")
