from datetime import datetime
import json
from typing import Optional, List, Dict
from sqlalchemy import String, Text, DateTime, ForeignKey, Integer, Table, Column, event
from sqlalchemy.orm import Mapped, mapped_column, relationship, backref, joinedload, validates
import enum

from sqlalchemy.orm import DeclarativeBase

from common.channel_config import get_channel_manager
from common.logging_config import get_logger
logger = get_logger(__name__)

class Base(DeclarativeBase):
    pass

class User(Base):
    """User model for tracking post authors."""
    __tablename__ = 'users'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    channel_preferences: Mapped[Optional[Dict]] = mapped_column(Text, 
        default=lambda: json.dumps({
            channel: channel in get_channel_manager().default_preferences
            for channel in get_channel_manager().get_channel_names()
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
    channel: Mapped[str] = mapped_column(String, default=None, server_default='private')

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

    @validates('channel')
    def validate_channel(self, key, channel):
        """Validate channel value against configuration."""
        if channel is None:
            channel = get_channel_manager().default_channel
            
        channel = channel.lower()
        if channel not in get_channel_manager().get_channel_names():
            raise ValueError(f"Invalid channel: {channel}")
        return channel

    def __init__(self, **kwargs):
        """Initialize email with default channel if none provided."""
        if 'channel' not in kwargs:
            kwargs['channel'] = get_channel_manager().default_channel
        super().__init__(**kwargs)

    @property
    def requires_auth(self) -> bool:
        """Whether this message requires authentication to view."""
        config = get_channel_manager().get_channel_config(self.channel)
        return config.requires_auth if config else True

    @property
    def is_public(self) -> bool:
        """Whether this message is publicly viewable."""
        config = get_channel_manager().get_channel_config(self.channel)
        return config.is_public if config else False

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
