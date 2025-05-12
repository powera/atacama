from flask import Blueprint, render_template, abort, flash, redirect, url_for, g, request
from sqlalchemy import select
from datetime import datetime
from common.database import db
from common.models import ReactWidget, User
from common.navigation import navigable
from common.logging_config import get_logger
from common.channel_config import get_channel_manager

from common.messages import get_user_allowed_channels

from common.auth import optional_auth, require_auth, require_admin

logger = get_logger(__name__)

widgets_bp = Blueprint('widgets', __name__)

@widgets_bp.route('/widget/<string:slug>')
@optional_auth
def view_widget(slug):
    """Display a React widget by slug."""
    with db.session() as session:
        widget = session.query(ReactWidget).filter_by(slug=slug).first()
        
        if not widget:
            abort(404)
        
        # Check channel access
        channel_manager = get_channel_manager()
        
        # Check if widget requires authentication
        #if widget.requires_auth and not g.user:
        if False: # Placeholder for actual authentication check
            flash("Please log in to view this widget.", 'error')
            return render_template('login.html')
        
        # Check domain restrictions
        from common.domain_config import get_domain_manager
        domain_manager = get_domain_manager()
        current_domain = g.current_domain
        
        if not domain_manager.is_channel_allowed(current_domain, widget.channel):
            flash("This widget is not available on this domain.", 'error')
            return redirect(url_for('content.message_stream'))
        
        # Check user channel access
        from common.messages import check_channel_access
        if not check_channel_access(widget.channel, user=g.user, ignore_preferences=True):
            flash("You don't have access to this widget.", 'error')
            return redirect(url_for('content.message_stream'))
        
        # Get channel configuration
        channel_config = channel_manager.get_channel_config(widget.channel)
        
        return render_template(
            'widget.html',
            widget=widget,
            channel_config=channel_config
        )
    

@widgets_bp.route('/widget/<string:slug>/edit', methods=['GET', 'POST'])
@require_admin
def edit_widget(slug):
    """Edit a React widget."""
    with db.session() as session:
        widget = session.query(ReactWidget).filter_by(slug=slug).first()
        
        if not widget:
            abort(404)
        
        # Check if user is the author or has admin access
        if not (g.user.id == widget.author_id or 
                (g.user.admin_channel_access and widget.channel in g.user.admin_channel_access)):
            flash("You don't have permission to edit this widget.", 'error')
            return redirect(url_for('widgets.view_widget', slug=slug))
        
        if request.method == 'POST':
            widget.title = request.form.get('title', widget.title)
            widget.description = request.form.get('description', widget.description)
            widget.code = request.form.get('code', widget.code)
            widget.last_modified_at = datetime.utcnow()
            
            session.commit()
            flash("Widget updated successfully!", 'success')
            return redirect(url_for('widgets.view_widget', slug=slug))
        
        return render_template(
            'widgets/edit_widget.html',
            widget=widget
        )
    

@widgets_bp.route('/widgets')
@navigable("React Widgets", description="View and manage React widgets", category="main")
@optional_auth
def list_widgets():
    """List all accessible React widgets."""
    allowed_channels = get_user_allowed_channels(user=g.user, ignore_preferences=True)
    
    with db.session() as session:
        query = session.query(ReactWidget).filter(ReactWidget.published == True)
        
        # Filter by allowed channels
        if not g.user or g.user.admin_channel_access is None:
            query = query.filter(ReactWidget.channel.in_(allowed_channels))
        
        widgets = query.order_by(ReactWidget.created_at.desc()).all()
        
        return render_template(
            'widgets/list.html',
            widgets=widgets
        )
    

@widgets_bp.route('/widget/new', methods=['GET', 'POST'])
@require_admin
def create_widget():
    """Create a new React widget."""
    if request.method == 'POST':
        slug = request.form.get('slug')
        title = request.form.get('title')
        code = request.form.get('code', '')
        description = request.form.get('description', '')
        channel = request.form.get('channel', 'private')
        
        # Validate slug uniqueness
        with db.session() as session:
            existing = session.query(ReactWidget).filter_by(slug=slug).first()
            if existing:
                flash("A widget with this slug already exists.", 'error')
                return render_template('widgets/create.html', form_data=request.form)
            
            widget = ReactWidget(
                slug=slug,
                title=title,
                code=code,
                description=description,
                channel=channel,
                author=g.user,
                published=False
            )
            
            session.add(widget)
            session.commit()
            
            flash("Widget created successfully!", 'success')
            return redirect(url_for('widgets.edit_widget', slug=slug))
    
    return render_template('widgets/create.html')


@widgets_bp.route('/widget/<string:slug>/publish', methods=['POST'])
@require_admin
def publish_widget(slug):
    """Publish a React widget."""
    with db.session() as session:
        widget = session.query(ReactWidget).filter_by(slug=slug).first()
        
        if not widget:
            abort(404)
        
        # Check if user is the author or has admin access
        if not (g.user.id == widget.author_id or 
                (g.user.admin_channel_access and widget.channel in g.user.admin_channel_access)):
            abort(403)
        
        widget.published = True
        widget.published_at = datetime.utcnow()
        session.commit()
        
        return {'status': 'success'}, 200