"""Articles blueprint for permanent content."""

from datetime import datetime
from flask import Blueprint, render_template, abort, g, request, redirect, url_for
from sqlalchemy import select

from common.auth import require_auth, optional_auth
from common.database import db
from common.models import Article
from common.channel_config import get_channel_manager
from common.messages import check_channel_access
from common.logging_config import get_logger

from aml_parser.parser import parse
from aml_parser.lexer import tokenize
from aml_parser.html_generator import generate_html

logger = get_logger(__name__)

articles_bp = Blueprint('articles', __name__)

@articles_bp.route('/p/<slug>')
@optional_auth
def view_article(slug: str):
    """View a single article by its slug."""
    with db.session() as session:
        article = session.query(Article).filter_by(slug=slug).first()
        
        if not article:
            abort(404)
            
        # Check if user has access to this channel
        if not check_channel_access(article.channel, g.user):
            if article.requires_auth:
                abort(403)
            
        # Get channel configuration for display
        channel_config = get_channel_manager().get_channel_config(article.channel)
        
        return render_template('articles/article.html',
                           article=article,
                           channel_config=channel_config)

@articles_bp.route('/articles/channel/<channel>')
@optional_auth
def article_stream(channel: str):
    """View stream of articles in a channel."""
    # Check channel exists and user has access
    if not check_channel_access(channel, g.user):
        abort(403)
        
    # Get configuration for all available channels
    channel_manager = get_channel_manager()
    
    with db.session() as session:
        # Get published articles for this channel
        articles = session.query(Article)\
            .filter_by(channel=channel, published=True)\
            .order_by(Article.published_at.desc())\
            .all()
            
        return render_template('articles/article_stream.html',
                           articles=articles,
                           current_channel=channel,
                           available_channels=channel_manager.get_channel_names(),
                           channel_config=channel_manager.get_channel_config(channel))

@articles_bp.route('/drafts')
@require_auth
def list_drafts():
    """List unpublished articles for the current user."""
    with db.session() as session:
        drafts = session.query(Article)\
            .filter_by(author=g.user, published=False)\
            .order_by(Article.last_modified_at.desc())\
            .all()
            
        return render_template('articles/drafts.html', articles=drafts)

@articles_bp.route('/p/<slug>/edit', methods=['GET', 'POST'])
@require_auth
def edit_article(slug: str):
    """Edit an existing article."""
    with db.session() as session:
        article = session.query(Article).filter_by(slug=slug).first()
        
        if not article:
            abort(404)
            
        # Only allow author to edit
        if article.author_id != g.user.id:
            abort(403)
            
        if request.method == 'POST':
            try:
                # Get user input
                title = request.form.get('title')
                content = request.form.get('content')
                channel = request.form.get('channel')
                publish = request.form.get('publish') == 'true'
                
                # Update article
                article.title = title
                article.content = content
                article.channel = channel
                
                # Handle publishing
                if publish and not article.published:
                    article.published = True
                    article.published_at = datetime.utcnow()
                
                tokens = tokenize(content)
                ast = parse(tokens)
                article.processed_content = generate_html(ast)
                
                article.last_modified_at = datetime.utcnow()
                session.commit()
                
                return redirect(url_for('articles.view_article', slug=article.slug))
                
            except Exception as e:
                logger.error(f"Error updating article: {str(e)}")
                return render_template('articles/edit_article.html',
                                   error=str(e),
                                   article=article,
                                   channels=get_channel_manager().channels)
        
        # GET request - show form
        return render_template('articles/edit_article.html',
                           article=article,
                           channels=get_channel_manager().channels)

@articles_bp.route('/submit/article', methods=['GET', 'POST'])
@require_auth
def submit_article():
    """Submit a new article."""
    if request.method == 'POST':
        # Get user input
        title = request.form.get('title')
        slug = request.form.get('slug')
        content = request.form.get('content')
        channel = request.form.get('channel')
        publish = request.form.get('publish') == 'true'
        
        try:
            with db.session() as session:
                # Create article
                article = Article(
                    title=title,
                    slug=slug,
                    content=content,
                    channel=channel,
                    published=publish,
                    published_at=datetime.utcnow() if publish else None,
                    author=g.user
                )
                
                tokens = tokenize(content)
                ast = parse(tokens)
                article.processed_content = generate_html(ast)
                
                session.add(article)
                session.commit()
                
                return redirect(url_for('articles.view_article', slug=article.slug))
                
        except Exception as e:
            logger.error(f"Error creating article: {str(e)}")
            return render_template('articles/submit_article.html', 
                               error=str(e),
                               channels=get_channel_manager().channels)
    
    # GET request - show form
    return render_template('articles/submit_article.html',
                       channels=get_channel_manager().channels)

# TODO: Add admin routes for article management when admin system is implemented
