"""
Debug information blueprint for system monitoring and diagnostics.

This blueprint provides endpoints for viewing system status, session information,
and other debug data. All endpoints require authentication.
"""

from flask import Blueprint, render_template, jsonify, current_app, session, request, redirect, url_for
import psutil
import os
import time
from datetime import datetime
from sqlalchemy import text

from common.logging_config import get_logger
logger = get_logger(__name__)

from common.auth import require_auth
from common.database import db

debug_bp = Blueprint('debug', __name__)

# Track server start time
SERVER_START_TIME = time.time()

def get_system_stats():
    """
    Get current system statistics.
    
    :return: Dictionary of system metrics
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
    
    :return: Dictionary of database metrics
    """
    with db.session() as db_session:
        # Test connection
        db_session.execute(text('SELECT 1'))
        
        # Get table statistics
        stats = {}
        for table in ['emails', 'quotes', 'email_quotes']:
            count = db_session.execute(
                text(f'SELECT COUNT(*) FROM {table}')
            ).scalar()
            stats[f'{table}_count'] = count
            
        return {
            'status': 'Connected',
            'table_stats': stats
        }


@debug_bp.route('/debug')
@require_auth
def debug_info():
    """Display debug information dashboard."""
    uptime = time.time() - SERVER_START_TIME
    uptime_formatted = str(datetime.utcfromtimestamp(uptime).strftime('%H:%M:%S'))
    
    system_stats = get_system_stats()
    db_stats = get_database_stats()
    
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
        session_data=session_data,
        config=safe_config
    )

@debug_bp.route('/debug/api')
@require_auth
def debug_api():
    """JSON endpoint for debug information."""
    uptime = time.time() - SERVER_START_TIME
    
    return jsonify({
        'uptime_seconds': uptime,
        'system': get_system_stats(),
        'database': get_database_stats()
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
    
    return redirect('/')

@debug_bp.route('/debug/logout')
def debug_logout():
    """Clear the debug user session."""
    if os.getenv('FLASK_ENV') != 'development':
        return "Debug logout only available in development mode", 403
        
    session.clear()
    return redirect('/')
