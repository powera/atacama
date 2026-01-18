from datetime import datetime
import json
from typing import Optional, List, Dict
from sqlalchemy import String, Text, DateTime, ForeignKey, Boolean, Integer, Table, Column, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship, backref, validates
import enum

from sqlalchemy.orm import DeclarativeBase

import constants
from common.config.channel_config import get_channel_manager
from common.base.logging_config import get_logger

from react_compiler import WidgetBuilder
from react_compiler.lib import sanitize_widget_title_for_component_name
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

    # DEPRECATED: Old single-token authentication columns (can be removed after migration)
    # Use UserToken model instead for multi-device support
    auth_token: Mapped[Optional[str]] = mapped_column(String, unique=True, nullable=True)
    auth_token_created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # One-to-many relationship with messages
    messages: Mapped[List["Message"]] = relationship("Message", back_populates="author")

    # One-to-many relationship with auth tokens (for multi-device support)
    auth_tokens: Mapped[List["UserToken"]] = relationship("UserToken", back_populates="user", cascade="all, delete-orphan")


class UserToken(Base):
    """Auth tokens for multi-device mobile/API authentication."""
    __tablename__ = 'user_tokens'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey('users.id'), nullable=False)
    token: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    device_info: Mapped[Optional[str]] = mapped_column(String)  # e.g., "iPhone 13", "Android Pixel"

    # Relationship back to user
    user: Mapped["User"] = relationship("User", back_populates="auth_tokens")


class MessageType(enum.Enum):
    EMAIL = "email"
    ARTICLE = "article"
    WIDGET = "widget"
    QUOTE = "quote"

class Message(Base):
    """Base class for all message types."""
    __tablename__ = 'messages'

    # Core fields
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    message_type: Mapped[MessageType] = mapped_column(Enum(MessageType), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_modified_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Channel and access
    channel: Mapped[str] = mapped_column(String, default='private', nullable=False)

    # Author/owner relationship
    author_id: Mapped[int] = mapped_column(Integer, ForeignKey('users.id'), nullable=False)
    author: Mapped["User"] = relationship("User", back_populates="messages")

    # Common validation
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
        """Initialize message with default channel if none provided."""
        if 'channel' not in kwargs:
            kwargs['channel'] = get_channel_manager().default_channel
        super().__init__(**kwargs)

    # Common properties
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

    # Polymorphic discriminator
    __mapper_args__ = {
        'polymorphic_identity': 'message',
        'polymorphic_on': message_type
    }


class Quote(Message):
    """Stores tracked quotes and their metadata."""
    __tablename__ = 'quotes'

    id: Mapped[int] = mapped_column(Integer, ForeignKey('messages.id'), primary_key=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    quote_type: Mapped[str] = mapped_column(String, nullable=False)
    original_author: Mapped[Optional[str]] = mapped_column(String)
    date: Mapped[Optional[str]] = mapped_column(String)  # Flexible format for historical dates
    source: Mapped[Optional[str]] = mapped_column(Text)
    commentary: Mapped[Optional[str]] = mapped_column(Text)  # For snowclone explanations or personal meanings

    # Relationship with emails that reference this quote
    emails: Mapped[List["Email"]] = relationship(
        "Email", 
        secondary='email_quotes', 
        back_populates="quotes",
        lazy="selectin"
    )

    __mapper_args__ = {
        'polymorphic_identity': MessageType.QUOTE
    }


class Email(Message):
    """Email model storing both original and processed content."""
    __tablename__ = 'emails'

    id: Mapped[int] = mapped_column(Integer, ForeignKey('messages.id'), primary_key=True)

    subject: Mapped[Optional[str]] = mapped_column(String)
    content: Mapped[str] = mapped_column(Text)
    preview_content: Mapped[str] = mapped_column(Text, nullable=True)  # Truncated at --MORE--
    processed_content: Mapped[str] = mapped_column(Text)

    # Chain relationships directly in Email
    parent_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey('emails.id'))
    children: Mapped[List["Email"]] = relationship(
        'Email',
        cascade="all, delete-orphan",
        backref=backref('parent', remote_side=[id]),
        foreign_keys=[parent_id]
    )

    # Annotation storage as JSON
    chinese_annotations: Mapped[Optional[Dict]] = mapped_column(Text)  # {position: {hanzi: str, pinyin: str, definition: str}}
    llm_annotations: Mapped[Optional[Dict]] = mapped_column(Text)  # {position: {type: str, content: str}}

    # Quote relationships
    quotes: Mapped[List["Quote"]] = relationship(
        "Quote", 
        secondary='email_quotes', 
        back_populates="emails",
        lazy="selectin"
    )

    __mapper_args__ = {
        'polymorphic_identity': MessageType.EMAIL
    }


# Association table for email-quote relationships
email_quotes = Table('email_quotes', Base.metadata,
    Column('email_id', Integer, ForeignKey('emails.id')),
    Column('quote_id', Integer, ForeignKey('quotes.id')),
    Column('created_at', DateTime, default=datetime.utcnow)
                     )


class Article(Message):
    __tablename__ = 'articles'

    id: Mapped[int] = mapped_column(Integer, ForeignKey('messages.id'), primary_key=True)

    # Article-specific fields
    slug: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    content: Mapped[str] = mapped_column(Text)
    processed_content: Mapped[str] = mapped_column(Text)

    # Publishing (Article-specific)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    published: Mapped[Optional[bool]] = mapped_column(Boolean, default=False)

    # Annotations (Article-specific)
    llm_annotations: Mapped[Optional[Dict]] = mapped_column(Text)

    @validates('slug')
    def validate_slug(self, key, slug):
        """Validate slug format."""
        if not slug or not isinstance(slug, str):
            raise ValueError("Slug must be a non-empty string")
        return slug.lower()

    __mapper_args__ = {
        'polymorphic_identity': MessageType.ARTICLE
    }


class ReactWidget(Message):
    """React widget model for storing interactive components."""
    __tablename__ = 'react_widgets'

    id: Mapped[int] = mapped_column(Integer, ForeignKey('messages.id'), primary_key=True)

    slug: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)

    code: Mapped[str] = mapped_column(Text)  # The React component code
    compiled_code: Mapped[Optional[str]] = mapped_column(Text)  # Compiled code for browser use
    dependencies: Mapped[Optional[str]] = mapped_column(Text)  # Comma-separated list
    data_file: Mapped[Optional[str]] = mapped_column(Text)  # The data file for the widget

    published: Mapped[Optional[bool]] = mapped_column(Boolean, default=False)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # Widget-specific settings
    props: Mapped[Optional[Dict]] = mapped_column(Text)  # JSON-encoded default props
    dependencies: Mapped[Optional[Dict]] = mapped_column(Text)  # External dependencies needed
    config: Mapped[Optional[Dict]] = mapped_column(Text)  # Widget configuration

    # Current active version
    active_version_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey('widget_versions.id'))

    # Relationship to versions
    versions: Mapped[List["WidgetVersion"]] = relationship("WidgetVersion", back_populates="widget", foreign_keys="[WidgetVersion.widget_id]", cascade="all, delete-orphan")
    active_version: Mapped[Optional["WidgetVersion"]] = relationship("WidgetVersion", foreign_keys=[active_version_id], post_update=True)

    def build(self, development_mode: bool = None):
        """Build the widget code into a browser-ready bundle."""        
        builder = WidgetBuilder()
        widget_name = self.title.replace(' ', '')

        # Determine development mode from environment if not explicitly provided
        if development_mode is None:
            development_mode = constants.is_development_mode()

        # We auto-detect the dependencies
        all_deps = builder.check_react_libraries(self.code)
        deps = all_deps["target_libraries"]
        self.dependencies = ",".join(deps)

        success, built_code, error = builder.build_widget(
            self.code, 
            widget_name,
            external_dependencies=deps,
            development_mode=development_mode,
            data_file=self.data_file
        )

        if success:
            logger.info(f"Widget {self.slug} built successfully.")
            self.compiled_code = built_code
        else:
            logger.warning(f"Widget build failed: {error}")
            self.compiled_code = None

        return success

    __mapper_args__ = {
        'polymorphic_identity': MessageType.WIDGET
    }
    @validates('slug')
    def validate_slug(self, key, slug):
        """Validate slug format."""
        if not slug or not isinstance(slug, str):
            raise ValueError("Slug must be a non-empty string")
        # Basic slug validation - alphanumeric plus hyphens
        import re
        if not re.match(r'^[a-z0-9]+(?:-[a-z0-9]+)*$', slug.lower()):
            raise ValueError("Slug format is invalid. Must contain only lowercase letters, numbers, and hyphens. Cannot start or end with hyphens, and cannot have consecutive hyphens. Examples: 'my-widget', 'widget123', 'test-app-2'")
        return slug.lower()


class WidgetVersion(Base):
    """Stores different versions of widget code, including AI-improved iterations."""
    __tablename__ = 'widget_versions'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    widget_id: Mapped[int] = mapped_column(Integer, ForeignKey('react_widgets.id'), nullable=False)

    # Version metadata
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)  # Auto-incrementing per widget
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Code and compilation
    code: Mapped[str] = mapped_column(Text, nullable=False)
    code_hash: Mapped[Optional[str]] = mapped_column(String(32))  # MD5 hash for de-duplication
    compiled_code: Mapped[Optional[str]] = mapped_column(Text)
    dependencies: Mapped[Optional[str]] = mapped_column(Text)  # Comma-separated list
    data_file: Mapped[Optional[str]] = mapped_column(Text) # The data file for the widget version

    # AI improvement tracking
    prompt_used: Mapped[Optional[str]] = mapped_column(Text)  # The prompt that generated this version
    previous_version_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey('widget_versions.id'))
    improvement_type: Mapped[Optional[str]] = mapped_column(String)  # 'canned', 'custom', 'manual'
    dev_comments: Mapped[Optional[str]] = mapped_column(Text)  # Developer notes about this version

    # AI generation metadata
    ai_model_used: Mapped[Optional[str]] = mapped_column(String)  # Which AI model was used
    ai_usage_stats: Mapped[Optional[Dict]] = mapped_column(Text)  # Token usage, cost, etc.

    # Status
    is_working: Mapped[Optional[bool]] = mapped_column(Boolean, default=None)  # Whether this version compiles/works
    build_error: Mapped[Optional[str]] = mapped_column(Text)  # Build error if any

    # Relationships
    widget: Mapped["ReactWidget"] = relationship("ReactWidget", back_populates="versions", foreign_keys=[widget_id])
    previous_version: Mapped[Optional["WidgetVersion"]] = relationship("WidgetVersion", remote_side=[id])

    def build(self, development_mode: bool = None):
        """Build this version of the widget code."""
        import hashlib

        builder = WidgetBuilder()
        widget_name = sanitize_widget_title_for_component_name(self.widget.title)

        # Determine development mode from environment if not explicitly provided
        if development_mode is None:
            development_mode = constants.is_development_mode()

        # Set code hash if not already set
        if not self.code_hash:
            self.code_hash = hashlib.md5(self.code.encode('utf-8')).hexdigest()

        # Auto-detect dependencies
        all_deps = builder.check_react_libraries(self.code)
        deps = all_deps["target_libraries"]
        self.dependencies = ",".join(deps)

        success, built_code, error = builder.build_widget(
            self.code, 
            widget_name,
            external_dependencies=deps,
            development_mode=development_mode,
            data_file=self.data_file
        )

        if success:
            logger.info(f"Widget version {self.id} built successfully.")
            self.compiled_code = built_code
            self.is_working = True
            self.build_error = None
        else:
            logger.warning(f"Widget version build failed: {error}")
            self.compiled_code = None
            self.is_working = False
            self.build_error = error

        return success