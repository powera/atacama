"""AML Parser - A parser for Atacama Markup Language."""

from .lexer import tokenize
from .parser import parse
from .html_generator import generate_html

def process_message(text, **kwargs):
    """Main entry point for message processing."""
    tokens = tokenize(text)
    ast = parse(tokens)
    return generate_html(ast, **kwargs)

__all__ = ['tokenize', 'parse', 'generate_html', 'process_message']
