"""Channel statistics functionality for viewing metrics about each channel."""

import json
from typing import Dict, List, Tuple
from collections import defaultdict
from datetime import datetime, timedelta

from flask import Blueprint, flash, g, redirect, render_template, request, session, url_for
from sqlalchemy import func, select, desc

import constants
from web.decorators.auth import optional_auth
from common.config.channel_config import AccessLevel, get_channel_manager
from models.database import db
from common.base.logging_config import get_logger
from models.models import Email, User
from models.messages import get_user_allowed_channels
from web.decorators.navigation import navigable

logger = get_logger(__name__)

statistics_bp = Blueprint('statistics', __name__)

@statistics_bp.route('/stats')
@optional_auth
@navigable(name="Channel Statistics", category="admin")
def channel_statistics():
    """Show statistics for all channels the user has access to."""
    allowed_channels = get_user_allowed_channels(g.user)
    
    # Get channel manager for config information
    channel_manager = get_channel_manager()
    
    channel_stats = []
    current_time = datetime.utcnow()
    
    with db.session() as db_session:
        for channel in allowed_channels:
            # Get channel configuration
            config = channel_manager.get_channel_config(channel)
            if not config:
                continue
                
            # Get basic channel stats
            total_count = db_session.execute(
                select(func.count()).select_from(Email).where(Email.channel == channel)
            ).scalar() or 0
            
            # Get count from past week
            week_ago = current_time - timedelta(days=7)
            week_count = db_session.execute(
                select(func.count()).select_from(Email)
                .where(Email.channel == channel)
                .where(Email.created_at >= week_ago)
            ).scalar() or 0
            
            # Get count from past month
            month_ago = current_time - timedelta(days=30)
            month_count = db_session.execute(
                select(func.count()).select_from(Email)
                .where(Email.channel == channel)
                .where(Email.created_at >= month_ago)
            ).scalar() or 0
            
            # Get most active authors
            top_authors = db_session.execute(
                select(Email.author_id, func.count().label('count'))
                .where(Email.channel == channel)
                .where(Email.author_id != None)
                .group_by(Email.author_id)
                .order_by(desc('count'))
                .limit(3)
            ).all()
            
            # Get author details
            author_details = []
            for author_id, count in top_authors:
                author = db_session.execute(
                    select(User).where(User.id == author_id)
                ).scalar_one_or_none()
                if author:
                    author_details.append({
                        'name': author.name,
                        'email': author.email,
                        'count': count
                    })
            
            # Get most recent message
            latest_message = db_session.execute(
                select(Email)
                .where(Email.channel == channel)
                .order_by(desc(Email.created_at))
                .limit(1)
            ).scalar_one_or_none()
            
            latest_date = latest_message.created_at if latest_message else None
            
            # Compile channel stats
            channel_stats.append({
                'name': channel,
                'display_name': config.get_display_name(),
                'description': config.description,
                'access_level': config.access_level.value,
                'group': config.group,
                'total_count': total_count,
                'week_count': week_count,
                'month_count': month_count,
                'authors': author_details,
                'latest_date': latest_date
            })
            
        # Get weekly activity data
        date_counts = defaultdict(int)
        past_30days = current_time - timedelta(days=30)
        activity_data = db_session.execute(
            select(
                func.date(Email.created_at).label('date'), 
                func.count().label('count')
            )
            .where(Email.created_at >= past_30days)
            .group_by('date')
            .order_by('date')
        ).all()
        
        for date, count in activity_data:
            date_counts[str(date)] = count
        
        # Sort channels by total count
        channel_stats.sort(key=lambda x: x['total_count'], reverse=True)
            
        return render_template(
            'channel_statistics.html',
            channel_stats=channel_stats,
            activity_data=dict(date_counts),
            channel_manager=channel_manager
        )
