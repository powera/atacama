from .lexer import tokenize
from .parser import parse
from .html_generator import generate_html

def process_message(text, annotations=None):
    """Main entry point for message processing."""
    tokens = tokenize(text)
    ast = parse(tokens)
    return generate_html(ast, annotations)
