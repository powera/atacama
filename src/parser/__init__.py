from parser.lexer import tokenize
from parser.parser import parse
from parser.html_generator import generate_html

def process_message(text, **kwargs):
    """Main entry point for message processing."""
    tokens = tokenize(text)
    ast = parse(tokens)
    return generate_html(ast, **kwargs)
