from datetime import datetime
from typing import Optional, List, Dict
from sqlalchemy import String, Text, DateTime, ForeignKey, Integer, Table, Column, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship, backref
import enum

from sqlalchemy.orm import DeclarativeBase

from common.logging_config import get_logger
logger = get_logger(__name__)

class Base(DeclarativeBase):
    pass

class Channel(enum.Enum):
    """Channel enum for message categorization."""
    PRIVATE = "private"  # default
    SANDBOX = "sandbox"  # For testing and experimentation
    SPORTS = "sports"
    POLITICS = "politics"
    RELIGION = "religion"
    CHESS = "chess"
    BOOKS = "books"
    TELEVISION = "television"
    TECH = "tech"
    LLM = "llm"
    MISC = "misc"

    @classmethod
    def from_string(cls, value: str) -> "Channel":
        """Convert string to Channel enum value, case-insensitive.
        
        :param value: String value to convert
        :return: Channel enum value
        :raises ValueError: If string doesn't match any channel
        """
        try:
            return cls[value.upper()]
        except KeyError:
            # Try matching on enum value instead
            for channel in cls:
                if channel.value == value.lower():
                    return channel
            raise ValueError(f"Invalid channel: {value}")

    @classmethod
    def get_default(cls) -> "Channel":
        """Get default channel value.
        
        :return: PRIVATE channel enum value
        """
        return cls.PRIVATE

class User(Base):
    """User model for tracking post authors."""
    __tablename__ = 'users'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # One-to-many relationship with emails
    emails: Mapped[List["Email"]] = relationship("Email", back_populates="author")

class Quote(Base):
    """Stores tracked quotes and their metadata."""
    __tablename__ = 'quotes'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    quote_type: Mapped[str] = mapped_column(String, nullable=False)
    author: Mapped[Optional[str]] = mapped_column(String)
    date: Mapped[Optional[str]] = mapped_column(String)  # Flexible format for historical dates
    source: Mapped[Optional[str]] = mapped_column(Text)
    commentary: Mapped[Optional[str]] = mapped_column(Text)  # For snowclone explanations or personal meanings
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Many-to-many relationship with emails where the quote appears
    emails: Mapped[List["Email"]] = relationship("Email", secondary='email_quotes', back_populates="quotes")

class Email(Base):
    """Email model storing both original and processed content."""
    __tablename__ = 'emails'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    subject: Mapped[Optional[str]] = mapped_column(String)
    content: Mapped[str] = mapped_column(Text)
    processed_content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    channel: Mapped[Channel] = mapped_column(Enum(Channel), default=Channel.PRIVATE, server_default=Channel.PRIVATE.value)

    author_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey('users.id'))
    author: Mapped[Optional["User"]] = relationship("User", back_populates="emails", lazy="selectin")

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
    quotes: Mapped[List[Quote]] = relationship(Quote, secondary='email_quotes', lazy="selectin", back_populates="emails")

# Association table for email-quote relationships
email_quotes = Table('email_quotes', Base.metadata,
    Column('email_id', Integer, ForeignKey('emails.id')),
    Column('quote_id', Integer, ForeignKey('quotes.id')),
    Column('created_at', DateTime, default=datetime.utcnow)
                     )

def get_or_create_user(db_session, request_user) -> User:
    """Get existing user or create new one."""
    db_user = db_session.query(User).filter_by(email=request_user["email"]).first()
    if not db_user:
        db_user = User(email=request_user["email"], name=request_user["name"])
        db_session.add(db_user)
        db_session.flush()
    return db_user
