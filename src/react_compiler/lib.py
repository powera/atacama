"""
Utility functions for React compilation and widget processing.
"""

import re


def sanitize_widget_title_for_component_name(widget_title: str) -> str:
    """
    Sanitize a widget title to create a valid React component name.
    
    React component names must:
    - Start with a capital letter
    - Contain only alphanumeric characters (A-Z, a-z, 0-9)
    - Not contain spaces, hyphens, colons, or other special characters
    
    Args:
        widget_title: The original widget title
        
    Returns:
        A sanitized component name suitable for React
    """
    # Remove all non-alphanumeric characters and replace with empty string
    sanitized = re.sub(r'[^A-Za-z0-9]', '', widget_title)
    
    # Ensure it starts with a capital letter
    if sanitized and sanitized[0].islower():
        sanitized = sanitized[0].upper() + sanitized[1:]
    elif not sanitized or not sanitized[0].isalpha():
        # If empty or starts with number, prepend 'Widget'
        sanitized = 'Widget' + sanitized
    
    # If still empty, use default
    if not sanitized:
        sanitized = 'Widget'
    
    return sanitized