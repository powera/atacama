from aml_parser.lexer import tokenize
from aml_parser.parser import parse
from aml_parser.html_generator import generate_html

def process_message(text, **kwargs):
    """Main entry point for message processing."""
    tokens = tokenize(text)
    ast = parse(tokens)
    return generate_html(ast, **kwargs)
