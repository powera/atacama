import re
from typing import Dict, Pattern

class ColorScheme:
    """Color scheme definitions and processing for email content."""
    
    COLORS = {
        'xantham': ('⌘', 'xantham'),  # sarcastic, overconfident
        'red': ('⚡', 'red'),          # forceful, certain
        'orange': ('⚔', 'orange'),    # counterpoint
        'yellow': ('⚜', 'yellow'),    # quotes
        'green': ('⚙', 'green'),      # technical explanations
        'teal': ('⚛', 'teal'),       # LLM output
        'blue': ('✧', 'blue'),       # voice from beyond
        'violet': ('⚶', 'violet'),    # serious
        'mogue': ('⚯', 'mogue'),      # actions taken
        'gray': ('◊', 'gray')        # past stories
    }
    
    def __init__(self):
        """Initialize color patterns for processing."""
        # Pattern for color tags starting a line (new paragraph)
        self.para_patterns: Dict[str, Pattern] = {
            color: re.compile(f'(?m)^[ \t]*<{color}>(.*?)(?:</{ color }>|$)', re.DOTALL)
            for color in self.COLORS.keys()
        }
        
        # Pattern for inline color tags
        self.inline_patterns: Dict[str, Pattern] = {
            color: re.compile(f'(?m)(?<!^[ \t]*)<{color}>(.*?)(?:</{ color }>|$)', re.DOTALL)
            for color in self.COLORS.keys()
        }
        
        # Pattern for << >> literal blocks
        self.literal_pattern = re.compile(r'<<(.*?)>>')
    
    def process_content(self, content: str) -> str:
        """
        Process text content and wrap color tags in HTML/CSS with sigils.
        
        :param content: Raw email content with color tags
        :return: Processed content with HTML/CSS styling
        """
        processed = content
        
        # Process paragraph-starting color tags
        for color, (sigil, class_name) in self.COLORS.items():
            matches = self.para_patterns[color].finditer(processed)
            for match in matches:
                text = match.group(1)
                replacement = f'<p class="color-{class_name}">{sigil} {text}</p>'
                processed = processed.replace(match.group(0), replacement)
        
        # Process inline color tags
        for color, (sigil, class_name) in self.COLORS.items():
            matches = self.inline_patterns[color].finditer(processed)
            for match in matches:
                text = match.group(1)
                replacement = f'<span class="color-{class_name}">{sigil} {text}</span>'
                processed = processed.replace(match.group(0), replacement)
        
        # Process literal blocks
        matches = self.literal_pattern.finditer(processed)
        for match in matches:
            text = match.group(1)
            replacement = f'<span class="literal-text">{text}</span>'
            processed = processed.replace(match.group(0), replacement)
        
        return processed
