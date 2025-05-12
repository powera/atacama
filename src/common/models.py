from datetime import datetime
import json
from typing import Optional, List, Dict
from sqlalchemy import String, Text, DateTime, ForeignKey, Boolean, Integer, Table, Column, event
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
    # One-to-many relationship with articles
    articles: Mapped[List["Article"]] = relationship("Article", back_populates="author")

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
    # Many-to-many relationship with articles where the quote appears
    articles: Mapped[List["Article"]] = relationship("Article", secondary='article_quotes', back_populates="quotes")


class Email(Base):
    """Email model storing both original and processed content."""
    __tablename__ = 'emails'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    subject: Mapped[Optional[str]] = mapped_column(String)
    content: Mapped[str] = mapped_column(Text)
    preview_content: Mapped[str] = mapped_column(Text, nullable=True)  # Truncated at --MORE--
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


class Article(Base):
    """Article model for permanent content."""
    __tablename__ = 'articles'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    content: Mapped[str] = mapped_column(Text)
    processed_content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    last_modified_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    channel: Mapped[str] = mapped_column(String, default=None, server_default='private')
    published: Mapped[Optional[bool]] = mapped_column(Boolean, default=False)

    author_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey('users.id'))
    author: Mapped[Optional["User"]] = relationship("User", back_populates="articles", lazy="selectin")
    
    # Annotation storage as JSON
    llm_annotations: Mapped[Optional[Dict]] = mapped_column(Text)  # {position: {type: str, content: str}}
    
    # Quote relationships
    quotes: Mapped[List[Quote]] = relationship(Quote, secondary='article_quotes', lazy="selectin", back_populates="articles")

    @validates('channel')
    def validate_channel(self, key, channel):
        """Validate channel value against configuration."""
        if channel is None:
            channel = get_channel_manager().default_channel
            
        channel = channel.lower()
        if channel not in get_channel_manager().get_channel_names():
            raise ValueError(f"Invalid channel: {channel}")
        return channel

    @validates('slug')
    def validate_slug(self, key, slug):
        """Validate slug format."""
        if not slug or not isinstance(slug, str):
            raise ValueError("Slug must be a non-empty string")
        # TODO: Add more comprehensive slug validation
        return slug.lower()

    def __init__(self, **kwargs):
        """Initialize article with default channel if none provided."""
        if 'channel' not in kwargs:
            kwargs['channel'] = get_channel_manager().default_channel
        if 'last_modified_at' not in kwargs:
            kwargs['last_modified_at'] = datetime.utcnow()
        super().__init__(**kwargs)

    @property
    def requires_auth(self) -> bool:
        """Whether this article requires authentication to view."""
        config = get_channel_manager().get_channel_config(self.channel)
        return config.requires_auth if config else True

    @property
    def is_public(self) -> bool:
        """Whether this article is publicly viewable."""
        config = get_channel_manager().get_channel_config(self.channel)
        return config.is_public if config else False

# Association table for article-quote relationships
article_quotes = Table('article_quotes', Base.metadata,
    Column('article_id', Integer, ForeignKey('articles.id')),
    Column('quote_id', Integer, ForeignKey('quotes.id')),
    Column('created_at', DateTime, default=datetime.utcnow)
)

class ReactWidget(Base):
    """React widget model for storing interactive components."""
    __tablename__ = 'react_widgets'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    code: Mapped[str] = mapped_column(Text)  # The React component code
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    last_modified_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    channel: Mapped[str] = mapped_column(String, default=None, server_default='private')
    published: Mapped[Optional[bool]] = mapped_column(Boolean, default=False)
    
    # Widget-specific settings
    props: Mapped[Optional[Dict]] = mapped_column(Text)  # JSON-encoded default props
    dependencies: Mapped[Optional[Dict]] = mapped_column(Text)  # External dependencies needed
    config: Mapped[Optional[Dict]] = mapped_column(Text)  # Widget configuration
    
    author_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey('users.id'))
    author: Mapped[Optional["User"]] = relationship("User", backref="react_widgets", lazy="selectin")
    
    @validates('channel')
    def validate_channel(self, key, channel):
        """Validate channel value against configuration."""
        if channel is None:
            channel = get_channel_manager().default_channel
            
        channel = channel.lower()
        if channel not in get_channel_manager().get_channel_names():
            raise ValueError(f"Invalid channel: {channel}")
        return channel
    
    @validates('slug')
    def validate_slug(self, key, slug):
        """Validate slug format."""
        if not slug or not isinstance(slug, str):
            raise ValueError("Slug must be a non-empty string")
        # Basic slug validation - alphanumeric plus hyphens
        import re
        if not re.match(r'^[a-z0-9]+(?:-[a-z0-9]+)*$', slug.lower()):
            raise ValueError("Slug must contain only lowercase letters, numbers, and hyphens")
        return slug.lower()
    
    def __init__(self, **kwargs):
        """Initialize widget with default channel if none provided."""
        if 'channel' not in kwargs:
            kwargs['channel'] = get_channel_manager().default_channel
        if 'last_modified_at' not in kwargs:
            kwargs['last_modified_at'] = datetime.utcnow()
        super().__init__(**kwargs)
    
    @property
    def requires_auth(self) -> bool:
        """Whether this widget requires authentication to view."""
        config = get_channel_manager().get_channel_config(self.channel)
        return config.requires_auth if config else True
    
    @property
    def is_public(self) -> bool:
        """Whether this widget is publicly viewable."""
        config = get_channel_manager().get_channel_config(self.channel)
        return config.is_public if config else False

def get_or_create_user(db_session, request_user) -> User:
    """Get existing user or create new one."""
    db_user = db_session.query(User).options(joinedload('*')).filter_by(email=request_user["email"]).first()
    if not db_user:
        db_user = User(email=request_user["email"], name=request_user["name"])
        db_session.add(db_user)
        db_session.flush()
    return db_user
