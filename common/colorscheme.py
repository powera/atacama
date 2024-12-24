import re
from typing import Dict, Pattern, Tuple, Optional, Match, List
import json

class ColorScheme:
    """Color scheme definitions and processing for email content."""
    
    COLORS = {
        'xantham': ('🔥', 'xantham'),  # sarcastic, overconfident
        'red': ('💡', 'red'),          # forceful, certain
        'orange': ('⚔️', 'orange'),    # counterpoint
        'yellow': ('💬', 'yellow'),    # quotes
        'green': ('⚙️', 'green'),      # technical explanations
        'teal': ('🤖', 'teal'),        # LLM output
        'blue': ('✨', 'blue'),        # voice from beyond
        'violet': ('📣', 'violet'),    # serious
        'mogue': ('🌎', 'mogue'),      # actions taken
        'gray': ('💭', 'gray'),        # past stories
        'hazel': ('🎭', 'hazel'),      # new color
    }
    
    def __init__(self):
        """Initialize patterns for processing."""
        # Pattern for color tags at start of line or after parenthesis
        self.color_pattern = re.compile(r'(?:^[ \t]*|(?<=\())<(\w+)>(.*?)(?:\)|$)')
        
        # Pattern for section breaks - strict matching
        self.section_break_pattern = re.compile(r'^----\r?\n', re.MULTILINE)
        
        # Pattern for literal text and list markers
        self.literal_text_pattern = re.compile(r'<<(.*?)>>')
        self.list_pattern = re.compile(r'^[ \t]*<<[ \t]*([*#>])[ \t]*(.+?)[ \t]*>>[ \t]*$', re.MULTILINE)
        
        # Pattern for URLs
        self.url_pattern = re.compile(
            r'https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+[^\s]*'
        )
        
        # Pattern for wikilinks
        self.wikilink_pattern = re.compile(r'\[\[([^]]+)\]\]')
        
        # Pattern for Chinese characters
        self.chinese_pattern = re.compile(r'[\u4e00-\u9fff]+')

    def process_color_line(self, line: str) -> str:
        """
        Process a single line containing color tags, handling nested parentheses.
        
        :param line: Line of text to process
        :return: Processed HTML with proper color and nesting
        """
        # First check for color at start of line
        start_match = re.match(r'^[ \t]*<(\w+)>(.*?)$', line)
        if not start_match:
            return self.process_literal_text(line)
            
        color, content = start_match.groups()
        if color not in self.COLORS:
            return self.process_literal_text(line)
            
        sigil, class_name = self.COLORS[color]
        
        # Process nested colors within parentheses
        def process_nested(text: str, depth: int = 0) -> str:
            result = []
            current_pos = 0
            paren_count = 0
            
            while current_pos < len(text):
                char = text[current_pos]
                
                if char == '(':
                    paren_count += 1
                    # Check for color tag after parenthesis
                    next_pos = current_pos + 1
                    color_match = re.match(r'[ \t]*<(\w+)>(.*?)(?:\)|$)', text[next_pos:])
                    if color_match and color_match.group(1) in self.COLORS:
                        inner_color = color_match.group(1)
                        inner_content = color_match.group(2)
                        inner_sigil, inner_class = self.COLORS[inner_color]
                        processed_inner = process_nested(inner_content, depth + 1)
                        result.append(
                            f'(<span class="color-{inner_class}">'
                            f'<span class="sigil">{inner_sigil}</span> {processed_inner}'
                            '</span>)'
                        )
                        current_pos = next_pos + len(color_match.group(0))
                        continue
                elif char == ')':
                    paren_count -= 1
                
                if paren_count < 0:
                    break
                    
                result.append(char)
                current_pos += 1
            
            return self.process_literal_text(''.join(result))
        
        processed_content = process_nested(content)
        return f'<p class="color-{class_name}"><span class="sigil">{sigil}</span> {processed_content}</p>'

    def process_literal_text(self, text: str) -> str:
        """
        Process literal text markers (<<text>>) and list markers.
        
        :param text: Text to process
        :return: Processed text with literal text spans
        """
        def replace_literal(match: Match) -> str:
            content = match.group(1)
            if content.strip() in ['*', '#', '>']:
                return match.group(0)  # Don't process list markers
            return f'<span class="literal-text">{content}</span>'
            
        return self.literal_text_pattern.sub(replace_literal, text)

    def process_lists(self, text: str) -> str:
        """Process list markers and create HTML lists."""
        def replace_list(match: Match) -> str:
            marker, content = match.groups()
            if marker == '*':
                return f'<li class="bullet-list">{content}</li>'
            elif marker == '#':
                return f'<li class="number-list">{content}</li>'
            else:  # '>'
                return f'<li class="arrow-list">{content}</li>'
        
        return self.list_pattern.sub(replace_list, text)

    def process_urls(self, text: str) -> str:
        """
        Convert URLs to clickable links.
        
        :param text: Text that may contain URLs
        :return: Text with URLs converted to HTML links
        """
        def replace_url(match: Match) -> str:
            url = match.group(0)
            return f'<a href="{url}" target="_blank">{url}</a>'
            
        return self.url_pattern.sub(replace_url, text)

    def process_wikilinks(self, text: str, base_url: str = "https://en.wikipedia.org/wiki/") -> str:
        """Convert [[wikilinks]] to HTML links."""
        def replace_link(match: Match) -> str:
            target = match.group(1)
            url = base_url + target.replace(' ', '_')
            return f'<a href="{url}" class="wikilink" target="_blank">{target}</a>'
            
        return self.wikilink_pattern.sub(replace_link, text)

    def process_chinese(self, text: str) -> Tuple[str, Dict]:
        """
        Process Chinese characters and generate annotations.
        
        :param text: Text containing Chinese characters
        :return: Tuple of (processed text, annotations dictionary)
        """
        annotations = {}
        positions = []
        
        for match in self.chinese_pattern.finditer(text):
            hanzi = match.group(0)
            pos = match.start()
            positions.append((pos, hanzi))
            
            # Simple pinyin generation for now
            # TODO: Replace with proper pinyin lookup
            annotations[hanzi] = {
                "pinyin": "pinyin",
                "definition": "definition"
            }
        
        return text, annotations

    def sanitize_html(self, text: str) -> str:
        """
        Basic HTML sanitization to prevent XSS while preserving our custom tags.
        
        :param text: Text to sanitize
        :return: Sanitized text
        """
        # First escape any existing HTML
        text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        
        # Then restore our custom color tags
        for color in self.COLORS.keys():
            text = text.replace(f'&lt;{color}&gt;', f'<{color}>')
        
        # Restore approved HTML tags
        approved_tags = ['p', 'span', 'hr', 'li', 'ul', 'ol', 'a']
        for tag in approved_tags:
            text = text.replace(f'&lt;{tag}', f'<{tag}')
            text = text.replace(f'&lt;/{tag}&gt;', f'</{tag}>')
            
        # Restore class attributes
        text = text.replace('&lt;p class=', '<p class=')
        text = text.replace('&lt;span class=', '<span class=')
        
        return text

    def extract_color_content(self, content: str, color: str) -> List[str]:
        """
        Extract content wrapped in specified color tags.
        
        :param content: Text content to process
        :param color: Color tag name to extract
        :return: List of text content found within the specified color tags
        """
        pattern = re.compile(
            f'^[ \t]*<{color}>(.*?)(?:\r?\n|$)',
            re.MULTILINE
        )
        
        matches = pattern.finditer(content)
        return [match.group(1).strip() for match in matches if match.group(1).strip()]

    def process_content(self, content: str, chinese_annotations: Optional[Dict] = None,
                       llm_annotations: Optional[Dict] = None) -> str:
        """Process text content and wrap color tags in HTML/CSS with sigils."""
        # First sanitize HTML
        processed = self.sanitize_html(content)
        
        # Process Chinese characters if no annotations provided
        if not chinese_annotations:
            processed, chinese_annotations = self.process_chinese(processed)
        
        # Split into sections
        sections = self.section_break_pattern.split(processed)
        processed_sections = []
        
        for section in sections:
            if not section.strip():
                continue
                
            # Process each line in the section
            lines = section.strip().split('\n')
            processed_lines = []
            
            for line in lines:
                if not line.strip():
                    continue
                processed_line = self.process_color_line(line.strip())
                processed_lines.append(processed_line)
            
            processed_section = '\n'.join(processed_lines)
            # Process remaining elements
            processed_section = self.process_lists(processed_section)
            processed_section = self.process_urls(processed_section)
            processed_section = self.process_wikilinks(processed_section)
            
            processed_sections.append(processed_section)
        
        return '\n<hr>\n'.join(processed_sections)
