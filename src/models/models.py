# Database Models Implementation

from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text, Boolean, ForeignKey, Enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import enum
from typing import Optional
from sqlalchemy.dialects.postgresql import JSONB

Base = declarative_base()

class SourceType(enum.Enum):
    RSS = "rss"
    HTML = "html"
    PDF = "pdf"

class SourceStatus(enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"

class ChangeStatus(enum.Enum):
    DETECTED = "detected"
    PROCESSED = "processed"
    VERIFIED = "verified"
    PENDING_EFFECTIVE = "pending_effective"
    ACTIVE = "active"
    WITHDRAWN = "withdrawn"

class JurisdictionLayer(enum.Enum):
    NATIONAL = "national"
    DISTRICT = "district"
    STATE = "state"

class Source(Base):
    __tablename__ = 'sources'
    
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    url = Column(String, nullable=False)
    jurisdiction = Column(String, nullable=False)
    layer = Column(Enum(JurisdictionLayer), nullable=False)
    source_type = Column(Enum(SourceType), nullable=False)
    status = Column(Enum(SourceStatus), default=SourceStatus.ACTIVE)
    last_checked = Column(DateTime, default=datetime.utcnow)
    last_changed = Column(DateTime)
    cadence_hours = Column(Integer, default=24)  # Default daily check
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationship to changes
    changes = relationship("Change", back_populates="source")

class Change(Base):
    __tablename__ = 'changes'
    
    id = Column(Integer, primary_key=True)
    source_id = Column(Integer, ForeignKey('sources.id'), nullable=False)
    content_hash = Column(String, nullable=False, index=True)
    content = Column(Text, nullable=False)
    detected_date = Column(DateTime, default=datetime.utcnow)
    effective_date = Column(DateTime)
    status = Column(Enum(ChangeStatus), default=ChangeStatus.DETECTED)
    ai_summary = Column(Text)
    confidence_score = Column(Integer)  # 0-100 confidence
    classification = Column(JSONB)
    reviewed_by = Column(String)
    reviewed_at = Column(DateTime)
    published_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    source = relationship("Source", back_populates="changes")
    reviews = relationship("ChangeReview", back_populates="change")

class ChangeReview(Base):
    __tablename__ = 'change_reviews'
    
    id = Column(Integer, primary_key=True)
    change_id = Column(Integer, ForeignKey('changes.id'), nullable=False)
    reviewer = Column(String, nullable=False)  # Pete, Randy, or Vern
    review_type = Column(String, nullable=False)  # "requirements", "hostile_review", "validation"
    comments = Column(Text)
    approved = Column(Boolean, default=False)
    reviewed_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationship
    change = relationship("Change", back_populates="reviews")

# Database setup
DATABASE_URL = "postgresql://user:password@localhost/bankruptcy_monitor"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def create_tables():
    """Create all tables"""
    Base.metadata.create_all(bind=engine)

if __name__ == "__main__":
    create_tables()
    print("Database tables created successfully")