"""Shared blueprints for blog functionality."""

from flask import Blueprint

# Main content blueprint - handles content display, submission, and articles
content_bp = Blueprint('content', 'web.blueprints.blog')

# Specialized blueprints for distinct functionality
quotes_bp = Blueprint('quotes', 'web.blueprints.blog')
feeds_bp = Blueprint('feeds', 'web.blueprints.blog')
statistics_bp = Blueprint('statistics', 'web.blueprints.blog')
widgets_bp = Blueprint('widgets', 'web.blueprints.blog')