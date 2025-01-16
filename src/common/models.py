from datetime import datetime
import json
from typing import Optional, List, Dict
from sqlalchemy import String, Text, DateTime, ForeignKey, Integer, Table, Column, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship, backref, joinedload
import enum

from sqlalchemy.orm import DeclarativeBase

from common.channel_config import get_channel_manager, init_channel_manager
from common.logging_config import get_logger
logger = get_logger(__name__)

class Base(DeclarativeBase):
    pass

class Channel(enum.Enum):
    """Channel enum for message categorization."""
    def __init_subclass__(cls, **kwargs):
        """Initialize enum members from configuration."""
        super().__init_subclass__(**kwargs)
        
    def __new__(cls):
        """Create enum members from channel configuration."""
        manager = get_channel_manager()
            
        # Create enum members from configuration
        members = {}
        for channel_name in manager.get_channel_names():
            enum_name = channel_name.upper()
            members[enum_name] = channel_name.lower()
            
        # Create the enum class with configured members
        return enum.Enum.__new__(cls, cls.__name__, members)
        
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
        
        :return: Default channel enum value from configuration
        """
        manager = get_channel_manager()
        return cls.from_string(manager.default_channel)

class User(Base):
    """User model for tracking post authors."""
    __tablename__ = 'users'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    channel_preferences: Mapped[Optional[Dict]] = mapped_column(Text, 
        default=lambda: json.dumps({
            "politics": False,
            "chess": False,
            "sports": True,
            "religion": True,
            "books": True,
            "television": True,
            "tech": True,
            "llm": True,
            "misc": True
        })
    )
    # Maps channel names to timestamps when access was granted
    # e.g. {"orinoco": "2025-01-15T14:30:00Z"}
    admin_channel_access: Mapped[Optional[Dict]] = mapped_column(Text, 
        default=lambda: json.dumps({}))

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
    db_user = db_session.query(User).options(joinedload('*')).filter_by(email=request_user["email"]).first()
    if not db_user:
        db_user = User(email=request_user["email"], name=request_user["name"])
        db_session.add(db_user)
        db_session.flush()
    return db_user
