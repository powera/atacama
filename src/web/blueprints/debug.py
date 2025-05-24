"""
Debug information blueprint for system monitoring and diagnostics.

This blueprint provides endpoints for viewing system status, session information,
and other debug data. All endpoints require authentication.
"""

import os
import time
from datetime import datetime

# Third-party imports
import psutil
from flask import Blueprint, render_template, jsonify, current_app, session, request, redirect, url_for, g
from sqlalchemy import text, engine

# Local imports
from web.decorators import require_auth, navigable
from models.database import db
from common.config.channel_config import get_channel_manager
from models.messages import check_channel_access
from common.base.logging_config import get_logger
from models.models import Article, ReactWidget, Email, Quote, MessageType

logger = get_logger(__name__)

debug_bp = Blueprint('debug', __name__)

# Track server start time
SERVER_START_TIME = time.time()

def get_system_stats():
    """
    Get current system statistics.
    
    :return: Dictionary containing CPU, memory and disk usage metrics
    """
    cpu_percent = psutil.cpu_percent(interval=0.1)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    
    return {
        'cpu_percent': cpu_percent,
        'memory_percent': memory.percent,
        'memory_used': memory.used,
        'memory_total': memory.total,
        'disk_percent': disk.percent,
        'disk_used': disk.used,
        'disk_total': disk.total
    }

def get_database_stats():
    """
    Get current database statistics.
    
    :return: Dictionary containing database connection status and table counts
    """
    try:
        with db.session() as db_session:
            # Test connection
            db_session.execute(text('SELECT 1'))
            
            # Get table statistics - handle both SQLite and Postgres
            stats = {}
            tables = [
                'emails', 'quotes', 'email_quotes', 'users', 
                'articles', 'react_widgets',
                'messages'
            ]
            
            for table in tables:
                try:
                    count = db_session.execute(
                        text(f'SELECT COUNT(*) FROM {table}')
                    ).scalar()
                    stats[f'{table}_count'] = count
                except Exception as e:
                    logger.warning(f"Could not get count for table {table}: {str(e)}")
                    stats[f'{table}_count'] = 'Error'
                    
            return {
                'status': 'Connected',
                'type': db._engine.dialect.name,
                'table_stats': stats
            }
    except Exception as e:
        logger.error(f"Database connection error: {str(e)}")
        return {
            'status': 'Error',
            'error': str(e),
            'table_stats': {}
        }

def get_channel_stats():
    """
    Get current channel configuration statistics.
    
    :return: Dictionary containing channel configuration information
    """
    channel_manager = get_channel_manager()
    channels = channel_manager.get_channel_names()
    
    # Get current user's channel access
    channel_access = {}
    for channel in channels:
        channel_access[channel] = check_channel_access(channel, g.user)
    
    return {
        'channels': channels,
        'public_channels': channel_manager.get_public_channels(),
        'default_channel': channel_manager.default_channel,
        'default_preferences': channel_manager.default_preferences,
        'channel_access': channel_access
    }

def get_article_stats():
    """
    Get current article statistics.
    
    :return: Dictionary containing article counts and status information
    """
    try:
        with db.session() as db_session:
            # Get total count
            total_count = db_session.query(Article).count()
            
            # Get published articles
            published_count = db_session.query(Article).filter(Article.published == True).count()
            
            # Get draft (unpublished) articles
            draft_count = db_session.query(Article).filter(Article.published == False).count()
            
            # Get articles by channel
            channels = {}
            for channel in get_channel_manager().get_channel_names():
                channel_count = db_session.query(Article).filter(Article.channel == channel).count()
                channels[channel] = channel_count
            
            # Get most recent article
            most_recent = db_session.query(Article).order_by(Article.created_at.desc()).first()
            most_recent_data = None
            if most_recent:
                most_recent_data = {
                    'id': most_recent.id,
                    'title': most_recent.title,
                    'slug': most_recent.slug,
                    'created_at': most_recent.created_at,
                    'published': most_recent.published
                }
            
            return {
                'total_count': total_count,
                'published_count': published_count,
                'draft_count': draft_count,
                'by_channel': channels,
                'most_recent': most_recent_data
            }
    except Exception as e:
        logger.error(f"Error getting article stats: {str(e)}")
        return {
            'error': str(e)
        }

def get_widget_stats():
    """
    Get current React widget statistics.
    
    :return: Dictionary containing widget counts and status information
    """
    try:
        with db.session() as db_session:
            # Get total count
            total_count = db_session.query(ReactWidget).count()
            
            # Get published widgets
            published_count = db_session.query(ReactWidget).filter(ReactWidget.published == True).count()
            
            # Get draft (unpublished) widgets
            draft_count = db_session.query(ReactWidget).filter(ReactWidget.published == False).count()
            
            # Get most recent widget
            most_recent = db_session.query(ReactWidget).order_by(ReactWidget.id.desc()).first()
            most_recent_data = None
            if most_recent:
                most_recent_data = {
                    'id': most_recent.id,
                    'title': most_recent.title,
                    'slug': most_recent.slug,
                    'published': most_recent.published
                }
            
            return {
                'total_count': total_count,
                'published_count': published_count,
                'draft_count': draft_count,
                'most_recent': most_recent_data
            }
    except Exception as e:
        logger.error(f"Error getting widget stats: {str(e)}")
        return {
            'error': str(e)
        }

def get_content_stats():
    """
    Get overall content statistics.
    
    :return: Dictionary containing content counts by type
    """
    try:
        with db.session() as db_session:
            # Count by message type
            email_count = db_session.query(Email).count()
            article_count = db_session.query(Article).count()
            widget_count = db_session.query(ReactWidget).count()
            
            # Count quotes
            quote_count = db_session.query(Quote).count()
            
            return {
                'emails': email_count,
                'articles': article_count,
                'widgets': widget_count,
                'quotes': quote_count,
                'total_content': email_count + article_count + widget_count
            }
    except Exception as e:
        logger.error(f"Error getting content stats: {str(e)}")
        return {
            'error': str(e)
        }

@debug_bp.route('/debug')
@require_auth
@navigable(name="Debug Information", category="admin")
def debug_info():
    """Display debug information dashboard."""
    uptime = time.time() - SERVER_START_TIME
    uptime_formatted = str(datetime.utcfromtimestamp(uptime).strftime('%H:%M:%S'))
    
    system_stats = get_system_stats()
    db_stats = get_database_stats()
    channel_stats = get_channel_stats()
    article_stats = get_article_stats()
    widget_stats = get_widget_stats()
    content_stats = get_content_stats()
    
    session_data = {
        key: session[key]
        for key in session.keys()
        if not key.startswith('_')  # Exclude Flask internal session keys
    }
    
    # Get Flask config (excluding sensitive values)
    safe_config = {
        key: value for key, value in current_app.config.items()
        if not any(sensitive in key.lower() 
                  for sensitive in ['secret', 'key', 'password', 'token'])
    }
    
    return render_template(
        'debug.html',
        uptime=uptime_formatted,
        system_stats=system_stats,
        db_stats=db_stats,
        channel_stats=channel_stats,
        article_stats=article_stats,
        widget_stats=widget_stats,
        content_stats=content_stats,
        session_data=session_data,
        config=safe_config
    )

@debug_bp.route('/debug/api')
@require_auth
def debug_api():
    """
    JSON endpoint for debug information.
    
    :return: JSON response containing system metrics
    """
    uptime = time.time() - SERVER_START_TIME
    
    return jsonify({
        'uptime_seconds': uptime,
        'system': get_system_stats(),
        'database': get_database_stats(),
        'channels': get_channel_stats(),
        'articles': get_article_stats(),
        'widgets': get_widget_stats(),
        'content': get_content_stats()
    })

@debug_bp.route('/debug/login', methods=['GET'])
def debug_login():
    """
    Development-only route to set a user as logged in with specified credentials.
    Only works if FLASK_ENV is set to 'development'.
    
    Query parameters:
        name: Display name for the debug user
        email: Email address for the debug user
        
    :return: Redirect to home page
    """
    if os.getenv('FLASK_ENV') != 'development':
        return "Debug login only available in development mode", 403
        
    name = request.args.get('name')
    email = request.args.get('email')
    
    if not name or not email:
        return "Both name and email parameters are required", 400
        
    session['user'] = {
        'name': name,
        'email': email,
        'provider': 'debug'
    }
    
    logger.info(f"Debug login for user {email}")
    return redirect('/')

@debug_bp.route('/debug/logout')
def debug_logout():
    """
    Clear the debug user session.
    
    :return: Redirect to home page
    """
    if os.getenv('FLASK_ENV') != 'development':
        return "Debug logout only available in development mode", 403
        
    session.clear()
    logger.info("Debug logout")
    return redirect('/')