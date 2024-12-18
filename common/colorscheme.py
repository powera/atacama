import re
from typing import Dict, Pattern

class ColorScheme:
    """Color scheme definitions and processing for email content."""
    
    COLORS = {
        'xantham': 'xantham',  # sarcastic, overconfident
        'red': 'red',          # forceful, certain
        'orange': 'orange',    # counterpoint
        'yellow': 'yellow',    # quotes
        'green': 'green',      # technical explanations
        'teal': 'teal',       # LLM output
        'blue': 'blue',       # voice from beyond
        'violet': 'violet',    # serious
        'mogue': 'mogue',      # actions taken
        'gray': 'gray'        # past stories
    }
    
    def __init__(self):
        """Initialize color patterns for processing."""
        self.color_patterns: Dict[str, Pattern] = {
            color: re.compile(f'<{color}>(.*?)(</{ color }>|$)', re.DOTALL)
            for color in self.COLORS.keys()
        }
    
    def process_content(self, content: str) -> str:
        """
        Process text content and wrap color tags in HTML/CSS.
        
        :param content: Raw email content with color tags
        :return: Processed content with HTML/CSS styling
        """
        processed = content
        
        for color, pattern in self.color_patterns.items():
            matches = pattern.finditer(content)
            for match in matches:
                text = match.group(1)
                replacement = f'<span class="color-{color}">{text}</span>'
                processed = processed.replace(match.group(0), replacement)
                
        return processed
