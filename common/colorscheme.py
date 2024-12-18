import re
from typing import Dict, Pattern

class ColorScheme:
    """Color scheme definitions and processing for email content."""
    
    COLORS = {
        'xantham': ('🔥', 'xantham'),  # sarcastic, overconfident
        'red': ('💡', 'red'),          # forceful, certain
        'orange': ('⚔️', 'orange'),    # counterpoint
        'yellow': ('💬', 'yellow'),    # quotes
        'green': ('⚙️', 'green'),      # technical explanations
        'teal': ('🤖', 'teal'),       # LLM output
        'blue': ('✨', 'blue'),       # voice from beyond
        'violet': ('📣', 'violet'),    # serious
        'mogue': ('🌎', 'mogue'),      # actions taken
        'gray': ('💭', 'gray')        # past stories
    }
    
    def __init__(self):
        """Initialize color patterns for processing."""
        # Pattern for color tags at the start of a line
        self.para_patterns: Dict[str, Pattern] = {
            color: re.compile(f'^[ \t]*<{color}>(.*?)(?:</{ color }>|$)', re.MULTILINE | re.DOTALL)
            for color in self.COLORS.keys()
        }
        
        # Pattern for all color tags (used with para_patterns to identify inline)
        self.all_patterns: Dict[str, Pattern] = {
            color: re.compile(f'<{color}>(.*?)(?:</{ color }>|$)', re.DOTALL)
            for color in self.COLORS.keys()
        }
        
        # Pattern for << >> literal blocks and section breaks
        self.literal_pattern = re.compile(r'<<(.*?)>>')
        self.section_break_pattern = re.compile(r'^[ \t]*<<[ \t]*-+[ \t]*>>[ \t]*$', re.MULTILINE)
    
    def process_content(self, content: str) -> str:
        """
        Process text content and wrap color tags in HTML/CSS with sigils.
        
        :param content: Raw email content with color tags
        :return: Processed content with HTML/CSS styling
        """
        processed = content
        
        # First process section breaks
        matches = self.section_break_pattern.finditer(processed)
        for match in matches:
            processed = processed.replace(match.group(0), '<hr class="section-break">')
        
        # Then process paragraph-starting color tags
        for color, (sigil, class_name) in self.COLORS.items():
            matches = self.para_patterns[color].finditer(processed)
            for match in matches:
                text = match.group(1)
                replacement = f'<p class="color-{class_name}"><span class="sigil">{sigil}</span> {text}</p>'
                processed = processed.replace(match.group(0), replacement)
        
        # Then process remaining (inline) color tags
        for color, (sigil, class_name) in self.COLORS.items():
            # Find all matches
            all_matches = list(self.all_patterns[color].finditer(processed))
            # Find paragraph matches that were already processed
            para_matches = list(self.para_patterns[color].finditer(content))
            
            # Process only the matches that weren't paragraph starts
            for match in all_matches:
                # Skip if this match corresponds to a paragraph start
                if not any(pm.start() == match.start() for pm in para_matches):
                    text = match.group(1)
                    replacement = f'<span class="color-{class_name}"><span class="sigil">{sigil}</span> {text}</span>'
                    processed = processed.replace(match.group(0), replacement)
        
        # Finally process remaining literal blocks (not section breaks)
        matches = self.literal_pattern.finditer(processed)
        for match in matches:
            text = match.group(1)
            if not text.strip('-'):  # Skip if it's just hyphens
                continue
            replacement = f'<span class="literal-text">{text}</span>'
            processed = processed.replace(match.group(0), replacement)
        
        return processed
