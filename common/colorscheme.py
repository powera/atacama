import re
from typing import Dict, Pattern, Tuple

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
            color: re.compile(f'^[ \t]*<{color}>(.*?)$', re.MULTILINE | re.DOTALL)
            for color in self.COLORS.keys()
        }
        
        # Pattern for all color tags
        self.all_patterns: Dict[str, Pattern] = {
            color: re.compile(f'<{color}>(.*?)$', re.DOTALL)
            for color in self.COLORS.keys()
        }
        
        # Pattern for section breaks (exactly 4 hyphens on a line)
        self.section_break_pattern = re.compile(r'^[ \t]*----[ \t]*\r?\n', re.MULTILINE)

        # Pattern for URLs
        self.url_pattern = re.compile(
            r'https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+[^\s]*'
        )
        
        # Pattern for nested colors using parentheses
        self.nested_color_pattern = re.compile(
            r'\([ \t]*<(\w+)>(.*?)[ \t]*\)'
        )

    def process_nested_colors(self, text: str) -> str:
        """
        Process nested color tags within parentheses.

        :param text: Text that may contain nested color tags
        :return: Processed text with nested color spans and styled parentheses
        """
        while True:
            match = self.nested_color_pattern.search(text)
            if not match:
                break

            color = match.group(1)
            inner_text = match.group(2)
            if color in self.COLORS:
                sigil, class_name = self.COLORS[color]
                # Include styled parentheses in the color span
                replacement = (
                    f'<span class="color-{class_name}">'
                    f'(<span class="sigil">{sigil}</span> {inner_text})'
                    f'</span>'
                )
                text = text.replace(match.group(0), replacement)

        return text

    def process_urls(self, text: str) -> str:
        """
        Convert URLs to clickable links.
        
        :param text: Text that may contain URLs
        :return: Text with URLs converted to HTML links
        """
        def replace_url(match):
            url = match.group(0)
            return f'<a href="{url}" target="_blank">{url}</a>'
            
        return self.url_pattern.sub(replace_url, text)

    def sanitize_html(self, text: str) -> str:
        """
        Sanitize HTML tags except for our color tags.
        
        :param text: Text that may contain HTML tags
        :return: Text with HTML tags escaped except for color tags
        """
        # Escape < and > that aren't part of our color tags
        safe_words = list(self.COLORS.keys())
        pattern = r'<(?!/?(?:' + '|'.join(safe_words) + r')\b)[^>]*>'
        return re.sub(pattern, lambda m: m.group().replace('<', '&lt;').replace('>', '&gt;'), text)

    def process_content(self, content: str) -> str:
        """
        Process text content and wrap color tags in HTML/CSS with sigils.

        :param content: Raw email content with color tags
        :return: Processed content with HTML/CSS styling
        """
        # First sanitize any HTML tags except our color tags
        processed = self.sanitize_html(content)

        # Process URLs after sanitization but before color processing
        processed = self.process_urls(processed)

        # Process paragraph-starting color tags
        for color, (sigil, class_name) in self.COLORS.items():
            matches = self.para_patterns[color].finditer(processed)
            for match in matches:
                text = match.group(1)
                # Process nested colors first
                text = self.process_nested_colors(text)
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
                    # Process nested colors
                    text = self.process_nested_colors(text)
                    replacement = f'<span class="color-{class_name}"><span class="sigil">{sigil}</span> {text}</span>'
                    processed = processed.replace(match.group(0), replacement)

        # Process section breaks after color processing
        processed = self.section_break_pattern.sub('<hr>\n', processed)

        # Process paragraphs - split on any sequence of newlines
        paragraphs = re.split(r'\n+', processed)
        processed_paragraphs = []

        for para in paragraphs:
            if not para.strip():
                continue
            # Skip if the paragraph is already wrapped in HTML tags
            if para.strip().startswith('<') and para.strip().endswith('>'):
                processed_paragraphs.append(para)
            else:
                # Wrap non-HTML content in paragraph tags
                processed_paragraphs.append(f'<p>{para.strip()}</p>')

        # Join with single newlines
        processed = '\n'.join(processed_paragraphs)

        return processed
