"""Shared blueprints for blog functionality."""

from flask import Blueprint
import os

# Get the blog module directory (parent of blueprints/)
blog_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Main content blueprint - handles content display, submission, and articles
content_bp = Blueprint(
    "content",
    __name__,
    template_folder=os.path.join(blog_dir, "templates"),
    static_folder=os.path.join(blog_dir, "static"),
)

# Specialized blueprints for distinct functionality
quotes_bp = Blueprint(
    "quotes",
    __name__,
    template_folder=os.path.join(blog_dir, "templates"),
    static_folder=os.path.join(blog_dir, "static"),
)
feeds_bp = Blueprint(
    "feeds",
    __name__,
    template_folder=os.path.join(blog_dir, "templates"),
    static_folder=os.path.join(blog_dir, "static"),
)
statistics_bp = Blueprint(
    "statistics",
    __name__,
    template_folder=os.path.join(blog_dir, "templates"),
    static_folder=os.path.join(blog_dir, "static"),
)
widgets_bp = Blueprint(
    "widgets",
    __name__,
    template_folder=os.path.join(blog_dir, "templates"),
    static_folder=os.path.join(blog_dir, "static"),
)
