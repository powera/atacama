from flask import Blueprint, render_template, abort, flash, redirect, url_for, g, request, jsonify
from sqlalchemy import select
from datetime import datetime
import hashlib
import threading
import time
import uuid
from models.database import db
from models.models import ReactWidget, User, WidgetVersion
from models.messages import check_channel_access
from atacama.decorators import navigable, optional_auth, require_auth, require_admin
from common.base.logging_config import get_logger
from common.config.channel_config import get_channel_manager
from common.config.domain_config import get_domain_manager
from common.llm.widget_improver import widget_improver
from common.llm.widget_initiator import widget_initiator
from common.llm.widget_schemas import DUAL_FILE_WIDGET_SCHEMA
from common.llm.types import Schema, SchemaProperty
from react_compiler.lib import sanitize_widget_title_for_component_name

from models.messages import get_user_allowed_channels
from .shared import widgets_bp

logger = get_logger(__name__)

# Global storage for improvement jobs
improvement_jobs = {}

# OpenAI API Schema Requirements:
# - All schema properties must be properly typed using Schema and SchemaProperty from common.llm.types
# - Missing parameters should be removed from schema definitions (not marked as optional with None defaults)
# - All parameters in OpenAI schemas should be marked as required=True unless explicitly optional
# - Use structured_data field from Response object for JSON schema responses
# - Empty string or None values should be handled explicitly before sending to API

def validate_llm_parameters(params: dict) -> dict:
    """
    Validate and clean parameters for OpenAI API calls.
    Removes None values and empty strings that could cause API issues.
    
    Args:
        params: Dictionary of parameters to validate
        
    Returns:
        Cleaned dictionary with None/empty values removed
    """
    cleaned = {}
    for key, value in params.items():
        # Remove None values and empty strings
        if value is not None and value != '':
            cleaned[key] = value
        # For boolean values, keep False explicitly
        elif isinstance(value, bool):
            cleaned[key] = value
    return cleaned


def generate_widget_content_hash(code: str, data_file: str = None) -> str:
    """
    Generate a composite hash for widget content including both code and data file.
    This ensures that changes to either the code or data file create a unique version.
    
    Args:
        code: The main widget code
        data_file: The data file content (can be None)
        
    Returns:
        MD5 hash of the combined content
    """
    # Create a composite string that includes both code and data file
    composite_content = code
    if data_file:
        composite_content += "|||DATA_FILE|||" + data_file
    
    return hashlib.md5(composite_content.encode('utf-8')).hexdigest()

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
            'widgets/widget.html',
            widget=widget,
            channel_config=channel_config,
            sanitized_component_name=sanitize_widget_title_for_component_name(widget.title)
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
            new_data_file = request.form.get('data_file', widget.data_file)
            
            # Handle empty data file (convert empty string to None)
            if new_data_file == '':
                new_data_file = None
            
            # Generate composite hash for both code and data file
            code_hash = generate_widget_content_hash(new_code, new_data_file)

            # Check if this exact combination of code and data file already exists as a version
            existing_version = session.query(WidgetVersion).filter_by(
                widget_id=widget.id,
                code_hash=code_hash
            ).first()

            # Only save a new version if the code is not in the WidgetVersion table
            if not existing_version:
                # Get the next version number
                max_version = session.query(WidgetVersion).filter_by(widget_id=widget.id).count()
                version_number = max_version + 1

                # Create new version
                version = WidgetVersion(
                    widget_id=widget.id,
                    version_number=version_number,
                    code=new_code,
                    code_hash=code_hash,
                    data_file=new_data_file,
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
            widget.data_file = new_data_file
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
        data_file = request.form.get('data_file', '')
        
        # Handle empty data file (convert empty string to None)
        if data_file == '':
            data_file = None

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
                published=False,
                data_file=data_file
            )

            session.add(widget)
            session.flush()  # To get widget ID

            # Create initial version if there's code
            if code.strip():
                code_hash = generate_widget_content_hash(code, data_file)
                initial_version = WidgetVersion(
                    widget_id=widget.id,
                    version_number=1,
                    code=code,
                    code_hash=code_hash,
                    data_file=data_file,
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
        use_advanced_model = data.get('use_advanced_model', False)
        target_files = data.get('target_files', ['main_code'])
        
        # Validate required parameters for OpenAI API
        if not prompt.strip():
            return jsonify({
                'success': False,
                'error': 'Improvement prompt is required'
            }), 400

        # Get the base code and data file
        if base_version == 'current':
            base_code = widget.code
            base_data_file = widget.data_file
        else:
            version = session.query(WidgetVersion).filter_by(id=base_version).first()
            if not version or version.widget_id != widget.id:
                return jsonify({
                    'success': False,
                    'error': 'Invalid version selected'
                }), 400
            base_code = version.code
            base_data_file = version.data_file

        # Extract widget data while in session context
        widget_title = widget.title

        # Generate unique job ID
        job_id = str(uuid.uuid4())

        # Initialize job status
        improvement_jobs[job_id] = {
            'status': 'processing',
            'progress': 'Starting AI improvement...',
            'result': None,
            'error': None,
            'started_at': time.time(),
            'widget_info': {
                'slug': slug,
                'title': widget_title
            }
        }

        # Start background thread for AI improvement
        def improve_in_background():
            try:
                logger.info(f"Starting background improvement for widget {slug}, job {job_id}")
                improvement_jobs[job_id]['progress'] = 'AI is analyzing and improving code...'

                result = widget_improver.improve_widget(
                    current_code=base_code,
                    prompt=prompt,
                    improvement_type=improvement_type,
                    widget_title=widget_title,
                    use_advanced_model=use_advanced_model,
                    data_file=base_data_file,
                    target_files=target_files
                )

                improvement_jobs[job_id]['status'] = 'completed'
                improvement_jobs[job_id]['result'] = result
                improvement_jobs[job_id]['progress'] = 'Improvement completed'
                improvement_jobs[job_id]['finished_at'] = time.time()
                logger.info(f"Completed background improvement for widget {slug}, job {job_id}")

            except Exception as e:
                logger.error(f"Error in background improvement for widget {slug}, job {job_id}: {str(e)}")
                improvement_jobs[job_id]['status'] = 'error'
                improvement_jobs[job_id]['error'] = str(e)
                improvement_jobs[job_id]['progress'] = 'Error occurred during improvement'
                improvement_jobs[job_id]['finished_at'] = time.time()

        thread = threading.Thread(target=improve_in_background)
        thread.daemon = True
        thread.start()

        return jsonify({
            'success': True,
            'job_id': job_id,
            'message': 'Improvement started in background'
        })


@widgets_bp.route('/widget/<string:slug>/improve_status/<string:job_id>', methods=['GET'])
@require_admin
def improve_status(slug, job_id):
    """Check the status of an improvement job."""
    with db.session() as session:
        widget = session.query(ReactWidget).filter_by(slug=slug).first()

        if not widget:
            abort(404)

        # Check permissions
        if not (g.user.id == widget.author_id or 
                (g.user.admin_channel_access and widget.channel in g.user.admin_channel_access)):
            abort(403)

        if job_id not in improvement_jobs:
            return jsonify({
                'success': False,
                'error': 'Job not found'
            }), 404

        job = improvement_jobs[job_id]

        # Clean up old completed/errored jobs (older than 24 hours)
        current_time = time.time()
        if job['status'] in ['completed', 'error'] and current_time - job['started_at'] > 86400:
            del improvement_jobs[job_id]
            return jsonify({
                'success': False,
                'error': 'Job has expired'
            }), 404

        response = {
            'success': True,
            'status': job['status'],
            'progress': job['progress']
        }

        if job['status'] == 'completed' and job['result']:
            response['result'] = job['result']
            # Mark job as accessed but don't delete it yet - let it show in admin jobs page
            job['accessed_at'] = current_time
        elif job['status'] == 'error':
            response['error'] = job['error']
            # Mark job as accessed but don't delete it yet - let it show in admin jobs page
            job['accessed_at'] = current_time

        return jsonify(response)


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
        data_file = data.get('data_file', None)
        code_hash = generate_widget_content_hash(code, data_file)
        prompt_used = data.get('prompt_used', '')
        improvement_type = data.get('improvement_type', 'custom')
        dev_comments = data.get('dev_comments', '')
        set_active = data.get('set_active', False)

        # Check for duplicate content (both code and data file combination)
        existing_version = session.query(WidgetVersion).filter_by(
            widget_id=widget.id,
            code_hash=code_hash
        ).first()

        if existing_version:
            return jsonify({
                'success': False,
                'error': f'This combination of code and data file already exists as version {existing_version.version_number}'
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
            data_file=data_file,
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
            widget.data_file = data_file
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
            data_file = widget.data_file
        else:
            version_obj = session.query(WidgetVersion).filter_by(id=version, widget_id=widget.id).first()
            if not version_obj:
                return jsonify({
                    'success': False,
                    'error': 'Version not found'
                }), 404
            code = version_obj.code
            data_file = version_obj.data_file

        return jsonify({
            'success': True,
            'code': code,
            'data_file': data_file
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
        test_data_file = request.form.get('data_file', widget.data_file)

        # Create a temporary widget object for testing
        test_widget = type('TestWidget', (), {
            'title': widget.title + ' (Test)',
            'slug': widget.slug + '-test',
            'code': test_code,
            'data_file': test_data_file,
            'compiled_code': None,
            'channel': widget.channel,
            'description': 'Test version of ' + widget.title,
            'published': False,
            'requires_auth': widget.requires_auth,
            'is_public': widget.is_public
        })()

        return render_template(
            'widgets/widget.html',
            widget=test_widget,
            channel_config=get_channel_manager().get_channel_config(widget.channel),
            sanitized_component_name=sanitize_widget_title_for_component_name(test_widget.title),
            test_mode=True
        )


@widgets_bp.route('/widget/initiate', methods=['GET', 'POST'])
@require_admin
def initiate_widget():
    """Create a new React widget using AI from a simple description."""
    if request.method == 'POST':
        # Handle form data instead of JSON
        slug = request.form.get('slug', '').strip()
        description = request.form.get('description', '').strip()
        title = request.form.get('title', '').strip()
        channel = request.form.get('channel', 'private')
        ai_model = request.form.get('ai_model', 'nano')
        use_advanced_model = ai_model == 'mini'
        
        # Build look_and_feel from form data
        look_and_feel = {
            'tone': request.form.get('tone', 'playful'),
            'visual': request.form.get('visual', 'clean'),
            'feedback': request.form.get('feedback', 'immediate')
        }
        widget_schema = DUAL_FILE_WIDGET_SCHEMA # Default to dual file schema

        # Validate inputs - all parameters are required for OpenAI API
        if not slug or not slug.strip():
            flash('Slug is required and cannot be empty', 'error')
            return render_template(
                'widgets/initiate.html',
                channel_manager=get_channel_manager(),
                look_and_feel_options=widget_initiator.LOOK_AND_FEEL_OPTIONS,
                form_data=request.form
            )

        if not description or not description.strip():
            flash('Description is required and cannot be empty', 'error')
            return render_template(
                'widgets/initiate.html',
                channel_manager=get_channel_manager(),
                look_and_feel_options=widget_initiator.LOOK_AND_FEEL_OPTIONS,
                form_data=request.form
            )

        # Validate widget_schema parameter - must be a valid Schema instance
        if not isinstance(widget_schema, (str, Schema)):
            flash('Invalid widget schema provided', 'error')
            return render_template(
                'widgets/initiate.html',
                channel_manager=get_channel_manager(),
                look_and_feel_options=widget_initiator.LOOK_AND_FEEL_OPTIONS,
                form_data=request.form
            )

        # Check if slug already exists
        with db.session() as session:
            existing = session.query(ReactWidget).filter_by(slug=slug).first()
            if existing:
                flash('A widget with this slug already exists', 'error')
                return render_template(
                    'widgets/initiate.html',
                    channel_manager=get_channel_manager(),
                    look_and_feel_options=widget_initiator.LOOK_AND_FEEL_OPTIONS,
                    form_data=request.form
                )

        # Generate widget title from slug if not provided
        if not title:
            title = ' '.join(word.capitalize() for word in slug.replace('-', ' ').replace('_', ' ').split())

        # Generate unique job ID
        job_id = str(uuid.uuid4())

        # Initialize job status
        improvement_jobs[job_id] = {
            'status': 'processing',
            'progress': 'Starting AI widget generation...',
            'result': None,
            'error': None,
            'started_at': time.time(),
            'widget_data': {
                'slug': slug,
                'title': title,
                'description': description,
                'channel': channel,
                'author_id': g.user.id
            }
        }

        # Start background thread for AI generation
        def initiate_in_background():
            try:
                logger.info(f"Starting background widget initiation for slug {slug}, job {job_id}")
                improvement_jobs[job_id]['progress'] = 'AI is generating widget code...'

                # Determine dual_file mode based on schema type
                dual_file = widget_schema == DUAL_FILE_WIDGET_SCHEMA if isinstance(widget_schema, Schema) else widget_schema == 'dual_file'

                # Use AI to generate the widget code
                result = widget_initiator.create_widget(
                    slug=slug,
                    description=description,
                    widget_title=title,
                    use_advanced_model=use_advanced_model,
                    look_and_feel=look_and_feel,
                    dual_file=dual_file
                )

                if not result['success']:
                    improvement_jobs[job_id]['status'] = 'error'
                    improvement_jobs[job_id]['error'] = f"Failed to generate widget: {result['error']}"
                    improvement_jobs[job_id]['progress'] = 'Error occurred during widget generation'
                    improvement_jobs[job_id]['finished_at'] = time.time()
                    return

                improvement_jobs[job_id]['progress'] = 'Creating widget in database...'

                # Create the widget in the database
                with db.session() as session:
                    try:
                        # Extract code based on whether it's dual-file or single-file
                        widget_code_content = ""
                        data_file_content = None

                        if isinstance(result['widget_code'], dict):
                            # Dual-file response
                            widget_code_content = result['widget_code']['code_file']['content']
                            data_file_content = result['widget_code']['data_file']['content']
                        else:
                            # Single-file response
                            widget_code_content = result['widget_code']

                        widget = ReactWidget(
                            slug=slug,
                            title=title,
                            code=widget_code_content,
                            description=description,
                            channel=channel,
                            author_id=improvement_jobs[job_id]['widget_data']['author_id'],
                            published=False,
                            data_file=data_file_content
                        )
                        session.add(widget)
                        session.flush()  # To get widget ID

                        # Create initial version
                        code_hash = hashlib.md5(widget_code_content.encode('utf-8')).hexdigest()
                        initial_version = WidgetVersion(
                            widget_id=widget.id,
                            version_number=1,
                            code=widget_code_content,
                            code_hash=code_hash,
                            data_file=data_file_content,
                            improvement_type='ai_generated',
                            dev_comments='Initial AI-generated widget from description',
                            ai_model_used='openai'
                        )

                        session.add(initial_version)
                        session.flush()

                        improvement_jobs[job_id]['progress'] = 'Building widget...'

                        # Build the initial version
                        build_success = initial_version.build()
                        logger.info(f"Created AI-generated widget {slug}, build success: {build_success}")

                        session.commit()

                        improvement_jobs[job_id]['status'] = 'completed'
                        improvement_jobs[job_id]['result'] = {
                            'widget_slug': slug,
                            'widget_title': title,
                            'build_success': build_success,
                            'usage_stats': result['usage_stats'],
                            'redirect_url': f'/widget/{slug}/edit'
                        }
                        improvement_jobs[job_id]['progress'] = 'Widget creation completed'
                        improvement_jobs[job_id]['finished_at'] = time.time()
                        logger.info(f"Completed background widget initiation for slug {slug}, job {job_id}")

                    except Exception as e:
                        logger.error(f"Error creating widget in database for job {job_id}: {str(e)}")
                        improvement_jobs[job_id]['status'] = 'error'
                        improvement_jobs[job_id]['error'] = f"Failed to create widget: {str(e)}"
                        improvement_jobs[job_id]['progress'] = 'Error occurred during database creation'
                        improvement_jobs[job_id]['finished_at'] = time.time()

            except Exception as e:
                logger.error(f"Error in background widget initiation for job {job_id}: {str(e)}")
                improvement_jobs[job_id]['status'] = 'error'
                improvement_jobs[job_id]['error'] = str(e)
                improvement_jobs[job_id]['progress'] = 'Error occurred during widget generation'
                improvement_jobs[job_id]['finished_at'] = time.time()

        thread = threading.Thread(target=initiate_in_background)
        thread.daemon = True
        thread.start()

        # Redirect to waiting page instead of returning JSON
        return redirect(url_for('widgets.widget_waiting', job_id=job_id))

    # GET request - show the initiation form
    return render_template(
        'widgets/initiate.html',
        channel_manager=get_channel_manager(),
        look_and_feel_options=widget_initiator.LOOK_AND_FEEL_OPTIONS
    )


@widgets_bp.route('/widget/initiate_status/<string:job_id>', methods=['GET'])
@require_admin
def initiate_status(job_id):
    """Check the status of a widget initiation job."""
    if job_id not in improvement_jobs:
        return jsonify({
            'success': False,
            'error': 'Job not found'
        }), 404

    job = improvement_jobs[job_id]

    # Clean up old completed/errored jobs (older than 24 hours)
    current_time = time.time()
    if job['status'] in ['completed', 'error'] and current_time - job['started_at'] > 86400:
        del improvement_jobs[job_id]
        return jsonify({
            'success': False,
            'error': 'Job has expired'
        }), 404

    response = {
        'success': True,
        'status': job['status'],
        'progress': job['progress']
    }

    if job['status'] == 'completed' and job['result']:
        response['result'] = job['result']
        # Mark job as accessed but don't delete it yet - let it show in admin jobs page
        job['accessed_at'] = current_time
    elif job['status'] == 'error':
        response['error'] = job['error']
        # Mark job as accessed but don't delete it yet - let it show in admin jobs page
        job['accessed_at'] = current_time

    return jsonify(response)


@widgets_bp.route('/widget/waiting/<string:job_id>')
@require_admin
def widget_waiting(job_id):
    """Show waiting page for widget creation with available information."""
    if job_id not in improvement_jobs:
        flash("Widget creation job not found or has expired.", 'error')
        return redirect(url_for('widgets.initiate_widget'))

    job = improvement_jobs[job_id]
    widget_data = job.get('widget_data', {})
    
    return render_template(
        'widgets/waiting.html',
        job_id=job_id,
        widget_data=widget_data,
        status=job['status'],
        progress=job['progress']
    )


@widgets_bp.route('/jobs')
@navigable(name="Jobs Status", category="admin")
@require_admin
def list_jobs():
    """List all jobs currently underway and recently completed."""
    current_time = time.time()
    
    # Clean up very old jobs (older than 24 hours) to prevent memory leaks
    jobs_to_delete = []
    for job_id, job_data in improvement_jobs.items():
        if job_data['status'] in ['completed', 'error'] and current_time - job_data['started_at'] > 86400:
            jobs_to_delete.append(job_id)
    
    for job_id in jobs_to_delete:
        del improvement_jobs[job_id]
    
    # Separate running and completed jobs
    running_jobs = []
    completed_jobs = []
    
    for job_id, job_data in improvement_jobs.items():
        # Calculate duration based on job status
        if job_data['status'] in ['completed', 'error'] and 'finished_at' in job_data:
            duration = job_data['finished_at'] - job_data['started_at']
            finished_at = datetime.fromtimestamp(job_data['finished_at'])
        else:
            duration = current_time - job_data['started_at']
            finished_at = None
            
        job_info = {
            'id': job_id,
            'status': job_data['status'],
            'progress': job_data['progress'],
            'started_at': datetime.fromtimestamp(job_data['started_at']),
            'finished_at': finished_at,
            'error': job_data.get('error'),
            'duration': duration
        }
        
        # Determine job type and add relevant info
        if 'widget_data' in job_data:
            # This is a widget initiation job
            job_info['type'] = 'Widget Creation'
            job_info['widget_slug'] = job_data['widget_data'].get('slug', 'Unknown')
            job_info['widget_title'] = job_data['widget_data'].get('title', 'Unknown')
        elif 'widget_info' in job_data:
            # This is a widget improvement job with widget info
            job_info['type'] = 'Widget Improvement'
            job_info['widget_slug'] = job_data['widget_info'].get('slug', 'Unknown')
            job_info['widget_title'] = job_data['widget_info'].get('title', 'Unknown')
        else:
            # This is a legacy widget improvement job without widget info
            job_info['type'] = 'Widget Improvement'
            job_info['widget_slug'] = 'Unknown'
            job_info['widget_title'] = 'Unknown'
        
        if job_data['status'] == 'processing':
            running_jobs.append(job_info)
        else:
            completed_jobs.append(job_info)
    
    # Sort completed jobs by start time (most recent first) and limit to 10
    completed_jobs.sort(key=lambda x: x['started_at'], reverse=True)
    completed_jobs = completed_jobs[:10]
    
    # Sort running jobs by start time (oldest first)
    running_jobs.sort(key=lambda x: x['started_at'])
    
    return render_template(
        'admin/jobs.html',
        running_jobs=running_jobs,
        completed_jobs=completed_jobs
    )