from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

class Email(Base):
    """Email model storing both original and processed content."""
    __tablename__ = 'emails'
    
    id = Column(Integer, primary_key=True)
    subject = Column(String(255))
    content = Column(Text)
    processed_content = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
