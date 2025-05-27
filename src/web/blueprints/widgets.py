from flask import Blueprint, render_template, abort, flash, redirect, url_for, g, request, jsonify
from sqlalchemy import select
from datetime import datetime
import hashlib
from models.database import db
from models.models import ReactWidget, User, WidgetVersion
from models.messages import check_channel_access
from web.decorators import navigable, optional_auth, require_auth, require_admin
from common.base.logging_config import get_logger
from common.config.channel_config import get_channel_manager
from common.config.domain_config import get_domain_manager
from common.llm.widget_improver import widget_improver

from models.messages import get_user_allowed_channels

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
        if widget.requires_auth and not g.user:
            flash("Please log in to view this widget.", 'error')
            return render_template('login.html')
        
        # Check domain restrictions
        domain_manager = get_domain_manager()
        current_domain = g.current_domain
        
        if not domain_manager.is_channel_allowed(current_domain, widget.channel):
            flash("This widget is not available on this domain.", 'error')
            return redirect(url_for('content.message_stream'))
        
        # Check user channel access
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
            new_code = request.form.get('code', widget.code)
            code_hash = hashlib.md5(new_code.encode('utf-8')).hexdigest()
            
            # Check if this exact code already exists as a version
            existing_version = session.query(WidgetVersion).filter_by(
                widget_id=widget.id,
                code_hash=code_hash
            ).first()
            
            # Only save a new version if the code is different
            if not existing_version and new_code != widget.code:
                # Get the next version number
                max_version = session.query(WidgetVersion).filter_by(widget_id=widget.id).count()
                version_number = max_version + 1
                
                # Create new version
                version = WidgetVersion(
                    widget_id=widget.id,
                    version_number=version_number,
                    code=new_code,
                    code_hash=code_hash,
                    improvement_type='manual',
                    dev_comments='Manual edit via form'
                )
                
                session.add(version)
                session.flush()  # To get the ID
                
                # Build the version
                build_success = version.build()
                logger.info(f"Created version {version_number} for widget {slug}, build success: {build_success}")
            
            # Update widget properties
            widget.title = request.form.get('title', widget.title)
            widget.description = request.form.get('description', widget.description)
            widget.code = new_code
            widget.last_modified_at = datetime.utcnow()

            session.commit()
            
            # Auto-build the widget after saving
            try:
                build_success = widget.build()
                session.commit()
                
                if build_success:
                    flash("Widget updated and built successfully!", 'success')
                else:
                    flash("Widget updated, but build failed. Check server logs.", 'warning')
            except Exception as e:
                logger.error(f"Widget build error during save: {str(e)}")
                flash("Widget updated, but build encountered an error.", 'warning')
            
            return redirect(url_for('widgets.view_widget', slug=slug))
        
        return render_template(
            'widgets/edit_widget.html',
            widget=widget,
            channel_manager=get_channel_manager()
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
            session.flush()  # To get widget ID
            
            # Create initial version if there's code
            if code.strip():
                code_hash = hashlib.md5(code.encode('utf-8')).hexdigest()
                initial_version = WidgetVersion(
                    widget_id=widget.id,
                    version_number=1,
                    code=code,
                    code_hash=code_hash,
                    improvement_type='manual',
                    dev_comments='Initial widget creation'
                )
                session.add(initial_version)
                session.flush()
                
                # Build the initial version
                build_success = initial_version.build()
                logger.info(f"Created initial version for widget {slug}, build success: {build_success}")
            
            session.commit()
            
            flash("Widget created successfully!", 'success')
            return redirect(url_for('widgets.edit_widget', slug=slug))
    
    return render_template('widgets/create.html')


@widgets_bp.route('/widget/<string:slug>/build', methods=['POST'])
@require_admin
def build_widget(slug):
    """Build a React widget."""
    with db.session() as session:
        widget = session.query(ReactWidget).filter_by(slug=slug).first()
        
        if not widget:
            abort(404)
        
        # Check permissions
        if not (g.user.id == widget.author_id or 
                (g.user.admin_channel_access and widget.channel in g.user.admin_channel_access)):
            abort(403)
        
        # Build the widget
        success = widget.build()
        session.commit()
        
    logger.info(f"Widget {slug} build status: {success}")
    if success:
        return jsonify({
            'status': 'success',
            'message': 'Widget built successfully!',
            'redirect': url_for('widgets.view_widget', slug=slug)
        }), 200
    else:
        return jsonify({
            'status': 'error',
            'message': f'Build failed!  Check server logs.'
        }), 400


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
        
        return jsonify({
            'status': 'success',
            'message': 'Widget published!'
        }), 200


@widgets_bp.route('/widget/<string:slug>/improve', methods=['GET', 'POST'])
@require_admin
def improve_widget(slug):
    """Improve a React widget using AI."""
    with db.session() as session:
        widget = session.query(ReactWidget).filter_by(slug=slug).first()
        
        if not widget:
            abort(404)
        
        # Check permissions
        if not (g.user.id == widget.author_id or 
                (g.user.admin_channel_access and widget.channel in g.user.admin_channel_access)):
            abort(403)
        
        if request.method == 'GET':
            # Show the improvement interface
            return render_template(
                'widgets/improve.html',
                widget=widget
            )
        
        # Handle POST request for AI improvement
        data = request.get_json()
        base_version = data.get('base_version', 'current')
        prompt = data.get('prompt', '')
        improvement_type = data.get('improvement_type', 'custom')
        
        # Get the base code
        if base_version == 'current':
            base_code = widget.code
        else:
            version = session.query(WidgetVersion).filter_by(id=base_version).first()
            if not version or version.widget_id != widget.id:
                return jsonify({
                    'success': False,
                    'error': 'Invalid version selected'
                }), 400
            base_code = version.code
        
        # Use AI to improve the widget
        result = widget_improver.improve_widget(
            current_code=base_code,
            prompt=prompt,
            improvement_type=improvement_type,
            widget_title=widget.title
        )
        
        return jsonify(result)


@widgets_bp.route('/widget/<string:slug>/save_version', methods=['POST'])
@require_admin
def save_version(slug):
    """Save a new version of the widget."""
    with db.session() as session:
        widget = session.query(ReactWidget).filter_by(slug=slug).first()
        
        if not widget:
            abort(404)
        
        # Check permissions
        if not (g.user.id == widget.author_id or 
                (g.user.admin_channel_access and widget.channel in g.user.admin_channel_access)):
            abort(403)
        
        data = request.get_json()
        code = data.get('code', '')
        code_hash = hashlib.md5(code.encode('utf-8')).hexdigest()
        prompt_used = data.get('prompt_used', '')
        improvement_type = data.get('improvement_type', 'custom')
        dev_comments = data.get('dev_comments', '')
        set_active = data.get('set_active', False)
        
        # Check for duplicate code
        existing_version = session.query(WidgetVersion).filter_by(
            widget_id=widget.id,
            code_hash=code_hash
        ).first()
        
        if existing_version:
            return jsonify({
                'success': False,
                'error': f'This code already exists as version {existing_version.version_number}'
            })
        
        # Get the next version number
        max_version = session.query(WidgetVersion).filter_by(widget_id=widget.id).count()
        version_number = max_version + 1
        
        # Create new version
        version = WidgetVersion(
            widget_id=widget.id,
            version_number=version_number,
            code=code,
            code_hash=code_hash,
            prompt_used=prompt_used,
            improvement_type=improvement_type,
            dev_comments=dev_comments,
            ai_model_used='openai'  # Could be made configurable
        )
        
        session.add(version)
        session.flush()  # To get the ID
        
        # Build the version
        build_success = version.build()
        
        if set_active and build_success:
            widget.active_version_id = version.id
            widget.code = code
            widget.compiled_code = version.compiled_code
            widget.dependencies = version.dependencies
            widget.last_modified_at = datetime.utcnow()
        
        session.commit()
        
        return jsonify({
            'success': True,
            'version_id': version.id,
            'version_number': version_number,
            'build_success': build_success
        })


@widgets_bp.route('/widget/<string:slug>/get_version_code', methods=['POST'])
@require_admin
def get_version_code(slug):
    """Get code for a specific version of the widget."""
    with db.session() as session:
        widget = session.query(ReactWidget).filter_by(slug=slug).first()
        
        if not widget:
            abort(404)
        
        # Check permissions
        if not (g.user.id == widget.author_id or 
                (g.user.admin_channel_access and widget.channel in g.user.admin_channel_access)):
            abort(403)
        
        data = request.get_json()
        version = data.get('version', 'current')
        
        if version == 'current':
            code = widget.code
        else:
            version_obj = session.query(WidgetVersion).filter_by(id=version, widget_id=widget.id).first()
            if not version_obj:
                return jsonify({
                    'success': False,
                    'error': 'Version not found'
                }), 404
            code = version_obj.code
        
        return jsonify({
            'success': True,
            'code': code
        })


@widgets_bp.route('/widget/<string:slug>/test_version', methods=['POST'])
@require_admin
def test_version(slug):
    """Test a version of widget code without saving."""
    with db.session() as session:
        widget = session.query(ReactWidget).filter_by(slug=slug).first()
        
        if not widget:
            abort(404)
        
        # Check permissions
        if not (g.user.id == widget.author_id or 
                (g.user.admin_channel_access and widget.channel in g.user.admin_channel_access)):
            abort(403)
        
        test_code = request.form.get('code', widget.code)
        
        # Create a temporary widget object for testing
        test_widget = type('TestWidget', (), {
            'title': widget.title + ' (Test)',
            'slug': widget.slug + '-test',
            'code': test_code,
            'compiled_code': None,
            'channel': widget.channel,
            'description': 'Test version of ' + widget.title,
            'published': False,
            'requires_auth': widget.requires_auth,
            'is_public': widget.is_public
        })()
        
        return render_template(
            'widget.html',
            widget=test_widget,
            channel_config=get_channel_manager().get_channel_config(widget.channel),
            test_mode=True
        )