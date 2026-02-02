"""AML Parser - A parser for Atacama Markup Language."""

import re

from .lexer import tokenize
from .parser import parse
from .html_generator import generate_html

def process_message(text, **kwargs):
    """Main entry point for message processing."""
    tokens = tokenize(text)
    ast = parse(tokens)
    return generate_html(ast, **kwargs)


# Pattern to match <<PRIVATE: ... >> markers (both inline and multi-line)
# Handles:
#   - <<PRIVATE: inline content >>
#   - <<<PRIVATE: multi-line content >>>
_PRIVATE_INLINE_PATTERN = re.compile(r'<<PRIVATE:\s*(.*?)\s*>>', re.DOTALL)
_PRIVATE_MULTILINE_PATTERN = re.compile(r'<<<PRIVATE:\s*(.*?)\s*>>>', re.DOTALL)


def extract_public_content(text: str) -> str:
    """
    Extract the public version of AML content by stripping <<PRIVATE: ... >> markers.

    Handles both inline and multi-line private markers:
    - <<PRIVATE: inline private text >>  -> removed entirely
    - <<<PRIVATE: multi-line private text >>>  -> removed entirely

    Args:
        text: The full AML content including private markers

    Returns:
        The public version with private content removed
    """
    if not text:
        return text

    # First remove multi-line private blocks (<<< >>>)
    result = _PRIVATE_MULTILINE_PATTERN.sub('', text)

    # Then remove inline private markers (<< >>)
    result = _PRIVATE_INLINE_PATTERN.sub('', result)

    # Clean up any resulting double whitespace or blank lines
    # Replace multiple consecutive blank lines with single blank line
    result = re.sub(r'\n\s*\n\s*\n', '\n\n', result)

    # Remove trailing whitespace from lines (but preserve structure)
    lines = result.split('\n')
    cleaned_lines = [line.rstrip() for line in lines]
    result = '\n'.join(cleaned_lines)

    return result.strip()


def has_private_content(text: str) -> bool:
    """
    Check if the given AML content contains any private markers.

    Args:
        text: The AML content to check

    Returns:
        True if there are <<PRIVATE: ... >> markers, False otherwise
    """
    if not text:
        return False

    return bool(_PRIVATE_INLINE_PATTERN.search(text) or _PRIVATE_MULTILINE_PATTERN.search(text))


__all__ = ['tokenize', 'parse', 'generate_html', 'process_message', 'extract_public_content', 'has_private_content']
