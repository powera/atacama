from datetime import datetime
from typing import Optional, List, Dict
from sqlalchemy import String, Text, DateTime, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass

class Quote(Base):
    """Stores tracked quotes and their metadata."""
    __tablename__ = 'quotes'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    author: Mapped[Optional[str]] = mapped_column(String)
    date: Mapped[Optional[str]] = mapped_column(String)  # Flexible format for historical dates
    source: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Many-to-many relationship with emails where the quote appears
    emails: Mapped[List["Email"]] = relationship(secondary='email_quotes')

class Email(Base):
    """Email model storing both original and processed content."""
    __tablename__ = 'emails'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    subject: Mapped[Optional[str]] = mapped_column(String)
    content: Mapped[str] = mapped_column(Text)
    processed_content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Chain relationships directly in Email
    parent_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey('emails.id'))
    children: Mapped[List["Email"]] = relationship(
        'Email',
        cascade="all, delete-orphan",
        backref=backref('parent', remote_side=[id])
    )
    
    # Annotation storage as JSON
    chinese_annotations: Mapped[Optional[Dict]] = mapped_column(Text)  # {position: {hanzi: str, pinyin: str, definition: str}}
    llm_annotations: Mapped[Optional[Dict]] = mapped_column(Text)  # {position: {type: str, content: str}}
    
    # Quote relationships
    quotes: Mapped[List[Quote]] = relationship(Quote, secondary='email_quotes')

# Association table for email-quote relationships
email_quotes = Table('email_quotes', Base.metadata,
    Column('email_id', Integer, ForeignKey('emails.id')),
    Column('quote_id', Integer, ForeignKey('quotes.id')),
    Column('created_at', DateTime, default=datetime.utcnow)
)
