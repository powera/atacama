#!/usr/bin/env python3

"""
Interactive session helper for Atacama.

This module provides a convenient set of pre-imported modules and utilities
for interactive Python sessions (e.g., via `python -i` or IPython).

Usage:
    python -i tools/interactive.py

    # Or from project root:
    python -c "from tools.interactive import *"

Available objects after import:
    - app: Flask application instance
    - db: Database manager
    - session: Function to create database sessions (use with `with session() as s:`)

    Models:
    - Email, Quote, User, Message, ReactWidget, Article

    Functions:
    - set_user(email, name=None): Set current user for the session
    - get_message(id): Get a message by ID
    - get_messages(channel=None, limit=10): Get recent messages
    - search_messages(query): Search messages by subject/content
    - reprocess_message(id): Reprocess a message's content
    - delete_message(id, cascade=False): Delete a message
    - set_message_parent(child_id, parent_id): Set parent-child relationship
    - set_message_channel(id, channel): Change a message's channel
    - list_channels(): List all available channels
    - export_messages(path): Export all messages to JSON

    Modules:
    - aml_parser: Atacama Markup Language parser
    - channel_manager: Channel configuration manager
"""

import os
import sys
from datetime import datetime
from pathlib import Path

# Add project src directory to Python path
_project_root = Path(__file__).parent.parent.absolute()
_src_dir = _project_root / 'src'
if str(_src_dir) not in sys.path:
    sys.path.insert(0, str(_src_dir))

# Initialize constants for production mode before other imports
import constants
constants.init_production()

# Standard library imports (commonly useful)
import json
import re

# Third-party imports
from flask import g

# Local imports - Models
from models import (
    db,
    Base,
    Email,
    Quote,
    User,
    Message,
    MessageType,
    ReactWidget,
    Article,
    get_message_by_id,
    get_message_chain,
    get_filtered_messages,
    get_or_create_user,
)

# Local imports - Configuration
from common.config.channel_config import get_channel_manager, init_channel_manager
from common.config.domain_config import get_domain_manager, init_domain_manager
from common.base.logging_config import get_logger

# Local imports - Parser
import aml_parser

# Local imports - Server
from atacama.server import create_app

# Local imports - Utilities
from util.db import (
    set_message_parent,
    delete_message,
    reprocess_message,
    set_message_channel,
    list_uncategorized_messages,
)
from util.export import export_messages

# Set up logging
logger = get_logger(__name__)

# Create Flask app and push application context
app = create_app()
_app_context = app.app_context()
_app_context.push()

# Initialize configuration managers
init_channel_manager()
init_domain_manager()

# Get channel manager for convenience
channel_manager = get_channel_manager()


def session():
    """
    Get a database session context manager.

    Usage:
        with session() as s:
            messages = s.query(Email).all()
    """
    return db.session()


def set_user(email: str, name: str = None) -> None:
    """
    Set the current user for the interactive session.

    Args:
        email: User's email address
        name: Optional display name (defaults to email username)
    """
    if name is None:
        name = email.split('@')[0]

    user_dict = {"email": email, "name": name}

    with db.session() as db_session:
        db_session.expire_on_commit = False
        g.user = get_or_create_user(db_session, user_dict)

    print(f"Switched to user: {g.user.name} <{g.user.email}>")


def get_message(message_id: int) -> Email:
    """
    Get a message by its ID.

    Args:
        message_id: The message ID

    Returns:
        Email object or None if not found
    """
    with db.session() as s:
        s.expire_on_commit = False
        return s.query(Email).get(message_id)


def get_messages(channel: str = None, limit: int = 10) -> list:
    """
    Get recent messages, optionally filtered by channel.

    Args:
        channel: Optional channel name to filter by
        limit: Maximum number of messages to return (default 10)

    Returns:
        List of Email objects
    """
    with db.session() as s:
        s.expire_on_commit = False
        query = s.query(Email).order_by(Email.created_at.desc())
        if channel:
            query = query.filter(Email.channel == channel.lower())
        return query.limit(limit).all()


def search_messages(query: str, limit: int = 20) -> list:
    """
    Search messages by subject or content.

    Args:
        query: Search string
        limit: Maximum number of results (default 20)

    Returns:
        List of matching Email objects
    """
    with db.session() as s:
        s.expire_on_commit = False
        search_pattern = f"%{query}%"
        return s.query(Email).filter(
            (Email.subject.ilike(search_pattern)) |
            (Email.content.ilike(search_pattern))
        ).order_by(Email.created_at.desc()).limit(limit).all()


def list_channels() -> list:
    """
    List all available channels.

    Returns:
        List of channel names
    """
    return channel_manager.get_channel_names()


def show_message(message_id: int) -> None:
    """
    Display a message's details.

    Args:
        message_id: The message ID to display
    """
    msg = get_message(message_id)
    if not msg:
        print(f"Message {message_id} not found")
        return

    print(f"ID: {msg.id}")
    print(f"Subject: {msg.subject}")
    print(f"Channel: {msg.channel}")
    print(f"Created: {msg.created_at}")
    print(f"Author: {msg.author.name if msg.author else 'Unknown'}")
    print(f"Parent ID: {msg.parent_id}")
    print("-" * 40)
    print(msg.content[:500] + "..." if len(msg.content) > 500 else msg.content)


def help_interactive() -> None:
    """Display help for the interactive session."""
    print(__doc__)


# Set default user
set_user("atacama@earlyversion.com")

# Print startup banner
print("\n" + "=" * 50)
print("  Atacama Interactive Shell")
print("=" * 50)
print("\nType help_interactive() for available commands")
print(f"Database: {constants.DB_PATH}")
print(f"Channels: {len(list_channels())} available")
print("")
