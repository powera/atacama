import re
from typing import Dict, Pattern, Tuple, Optional, Match
import json
from functools import lru_cache

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
        # Basic color pattern, only matching specific color names at start of line or in parentheses
        color_names = '|'.join(self.COLORS.keys())
        self.color_pattern = re.compile(
            fr'(?:^[ \t]*<({color_names})>(.+?)(?:\r?\n|$))|'  # Start of line
            fr'\([ \t]*<({color_names})>(.*?)[ \t]*\)',  # In parentheses
            re.MULTILINE | re.DOTALL
        )
        
        # Pattern for inline color tags
        self.inline_color_pattern = re.compile(
            fr'<({color_names})>(.+?)(?:\r?\n|$)',
            re.MULTILINE | re.DOTALL
        )
        
        self.chinese_pattern = re.compile(r'[\u4e00-\u9fff]+')
        self.section_break_pattern = re.compile(r'^[ \t]*----[ \t]*$', re.MULTILINE)
        self.list_pattern = re.compile(r'^[ \t]*([*#>])[ \t]+(.+?)[ \t]*$', re.MULTILINE)
        self.url_pattern = re.compile(r'https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+[^\s]*')
        self.wikilink_pattern = re.compile(r'\[\[([^]]+)\]\]')
        self.paragraph_pattern = re.compile(r'\n\s*\n+')

    def sanitize_html(self, text: str) -> str:
        """
        Sanitize HTML while preserving our special color tags for later processing.
        
        :param text: Text to sanitize
        :return: Text with HTML escaped but color tags preserved
        """
        # First preserve our special color tags by replacing them with unique tokens
        preserved = {}
        counter = 0
        
        # Save color tags with a unique token
        for color in self.COLORS.keys():
            # Find all instances of <color> tags
            for match in re.finditer(f'<{color}>', text):
                token = f'__PRESERVED_COLOR_{counter}__'
                preserved[token] = match.group(0)
                text = text.replace(match.group(0), token)
                counter += 1
        
        # Now escape all HTML
        text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        
        # Restore our preserved color tags
        for token, original in preserved.items():
            text = text.replace(token, original)
        
        return text

    def wrap_chinese(self, text: str, annotations: Optional[Dict] = None) -> str:
        """
        Wrap Chinese characters in annotated spans.
        
        :param text: Text containing Chinese characters
        :param annotations: Optional dictionary of annotations
        :return: Text with wrapped Chinese characters
        """
        def replacer(match: Match) -> str:
            hanzi = match.group(0)
            if annotations and hanzi in annotations:
                ann = annotations[hanzi]
                pinyin = ann["pinyin"].replace('"', '&quot;')
                definition = ann["definition"].replace('&', '&amp;').replace('"', '&quot;')
                return (f'<span class="annotated-chinese" '
                       f'data-pinyin="{pinyin}" '
                       f'data-definition="{definition}">'
                       f'{hanzi}</span>')
            return f'<span class="annotated-chinese">{hanzi}</span>'
            
        return self.chinese_pattern.sub(replacer, text)

    def process_colors(self, text: str) -> str:
        """
        Process all color tags.
        
        :param text: Text that may contain color tags
        :return: Processed text with color spans and sigils
        """
        def replace_color(match: Match) -> str:
            # Extract matched groups
            para_color, para_text, nested_color, nested_text = match.groups()
            
            # Determine which type matched and get the content
            color = para_color or nested_color
            content = para_text or nested_text
            
            if not color or color not in self.COLORS:
                return match.group(0)
                
            sigil, class_name = self.COLORS[color]
            
            # Handle nested colors (with parentheses)
            if nested_color:
                return (f'<span class="color-{class_name}">'
                       f'(<span class="sigil">{sigil}</span> {content})'
                       f'</span>')
            
            # Handle paragraph-level colors
            return (f'<p class="color-{class_name}">'
                   f'<span class="sigil">{sigil}</span> {content}'
                   f'</p>')
                   
        # First process paragraph and nested colors
        processed = self.color_pattern.sub(replace_color, text)
        
        # Then process any remaining inline colors
        def replace_inline(match: Match) -> str:
            color, content = match.groups()
            if color not in self.COLORS:
                return match.group(0)
            sigil, class_name = self.COLORS[color]
            return (f'<span class="color-{class_name}">'
                   f'<span class="sigil">{sigil}</span> {content}'
                   f'</span>')
                   
        return self.inline_color_pattern.sub(replace_inline, processed)

    def process_lists(self, text: str) -> str:
        """
        Convert list markers to HTML lists with appropriate classes.
        
        :param text: Text containing list items
        :return: Processed text with HTML lists
        """
        lines = text.split('\n')
        processed_lines = []
        current_list = []
        list_type = None

        for line in lines:
            match = self.list_pattern.match(line)
            if match:
                marker, content = match.groups()
                current_type = {
                    '*': 'bullet-list',
                    '#': 'number-list',
                    '>': 'arrow-list'
                }[marker]
                
                if list_type != current_type:
                    if current_list:
                        processed_lines.append('<ul>')
                        processed_lines.extend(current_list)
                        processed_lines.append('</ul>')
                        current_list = []
                    list_type = current_type
                
                current_list.append(f'<li class="{current_type}">{content}</li>')
            else:
                if current_list:
                    processed_lines.append('<ul>')
                    processed_lines.extend(current_list)
                    processed_lines.append('</ul>')
                    current_list = []
                    list_type = None
                processed_lines.append(line)

        if current_list:
            processed_lines.append('<ul>')
            processed_lines.extend(current_list)
            processed_lines.append('</ul>')

        return '\n'.join(processed_lines)

    def process_urls(self, text: str) -> str:
        """Convert URLs to clickable links."""
        def replacer(match: Match) -> str:
            url = match.group(0)
            sanitized_url = url.replace('"', '%22')
            return f'<a href="{sanitized_url}" target="_blank" rel="noopener noreferrer">{url}</a>'
        return self.url_pattern.sub(replacer, text)

    def process_wikilinks(self, text: str) -> str:
        """Convert [[wikilinks]] to HTML links."""
        def replacer(match: Match) -> str:
            target = match.group(1)
            url = target.replace(' ', '_').replace('"', '%22')
            return f'<a href="https://en.wikipedia.org/wiki/{url}" class="wikilink" target="_blank">{target}</a>'
        return self.wikilink_pattern.sub(replacer, text)

    def process_content(self, content: str, chinese_annotations: Optional[Dict] = None,
                       llm_annotations: Optional[Dict] = None) -> str:
        """
        Process text content with all features.
        
        :param content: Raw text content to process
        :param chinese_annotations: Optional Chinese character annotations
        :param llm_annotations: Optional LLM annotations
        :return: Fully processed HTML content
        """
        if not content:
            return ""

        # First process URLs and wikilinks (before HTML escaping)
        text = self.process_urls(content)
        text = self.process_wikilinks(text)
        
        # Then sanitize HTML to prevent XSS
        text = self.sanitize_html(text)
        
        # Process Chinese annotations
        text = self.wrap_chinese(text, chinese_annotations)
        
        # Process LLM annotations if provided
        if llm_annotations:
            for pos, annotation in llm_annotations.items():
                text = text[:int(pos)] + "🔍✨💡" + text[int(pos):]
        
        # Process lists
        text = self.process_lists(text)
        
        # Process all color tags
        text = self.process_colors(text)
        
        # Process section breaks
        text = self.section_break_pattern.sub('<hr>', text)
        
        # Wrap remaining content in paragraphs
        paragraphs = []
        for para in text.split('\n\n'):
            if para.strip():
                if not (para.strip().startswith('<') and (
                    para.strip().startswith('<p') or 
                    para.strip().startswith('<ul') or 
                    para.strip().startswith('<hr')
                )):
                    para = f'<p>{para.strip()}</p>'
                paragraphs.append(para.strip())
        
        return '\n'.join(paragraphs)

    def extract_color_content(self, content: str, color: str) -> list[str]:
        """
        Extract content from specified color tags.
        
        :param content: Text content to process
        :param color: Color tag name to extract
        :return: List of text content found within the specified color tags
        """
        pattern = re.compile(
            fr'<{color}>(.*?)(?:\r?\n|$)',
            re.MULTILINE | re.DOTALL
        )
        matches = pattern.finditer(content)
        return [match.group(1).strip() for match in matches if match.group(1).strip()]
