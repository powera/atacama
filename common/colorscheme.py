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
        self.chinese_pattern = re.compile(r'[\u4e00-\u9fff]+')
        self.section_break_pattern = re.compile(r'^[ \t]*----[ \t]*$', re.MULTILINE)
        self.list_pattern = re.compile(r'^[ \t]*([*#>])[ \t]+(.+?)[ \t]*$', re.MULTILINE)
        self.url_pattern = re.compile(r'https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+[^\s]*')
        self.wikilink_pattern = re.compile(r'\[\[([^]]+)\]\]')
        self.paragraph_pattern = re.compile(r'\n\s*\n+')
        self.linebreak_pattern = re.compile(r'\n')
        
        # Pattern for nested colors using parentheses
        self.nested_color_pattern = re.compile(
            r'\([ \t]*<(\w+)>(.*?)[ \t]*\)'
        )

        # Color patterns
        self.color_start_pattern = re.compile(r'<(\w+)>')
        self.color_end_pattern = re.compile(r'</(\w+)>')

    def sanitize_html(self, text: str) -> str:
        """
        Basic HTML sanitization to prevent XSS while preserving custom tags.
        
        :param text: Text to sanitize
        :return: Sanitized text
        """
        # Define tags to preserve
        preserve_tags = [
            # Color-related tags
            (r'<span class="color-[^"]*"[^>]*>', '</span>'),
            (r'<span class="sigil"[^>]*>', '</span>'),
            # List tags
            (r'<ul[^>]*>', '</ul>'),
            (r'<li class="[^"]*"[^>]*>', '</li>'),
            # Chinese annotation tags
            (r'<span class="annotated-chinese"[^>]*>', '</span>'),
            # Links and basic formatting
            (r'<a href="[^"]*"[^>]*>', '</a>'),
            (r'<p[^>]*>', '</p>'),
            (r'<hr[^>]*/?>', ''),
            (r'<br[^>]*/?>', '')
        ]

        # First escape everything
        text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        
        # Then restore preserved tags
        for start_pattern, end_tag in preserve_tags:
            # Find all preserved tags
            parts = []
            last_end = 0
            for match in re.finditer(start_pattern.replace('&lt;', '<').replace('&gt;', '>'), text):
                start_pos = match.start()
                end_tag_pos = text.find(end_tag.replace('&lt;', '<').replace('&gt;', '>'), start_pos)
                if end_tag_pos != -1:
                    # Add text before the tag
                    parts.append(text[last_end:start_pos])
                    # Add the tag content without escaping
                    content = text[start_pos:end_tag_pos + len(end_tag)]
                    parts.append(content.replace('&lt;', '<').replace('&gt;', '>'))
                    last_end = end_tag_pos + len(end_tag)
            parts.append(text[last_end:])
            text = ''.join(parts)
        
        return text

    def wrap_chinese(self, text: str, annotations: Optional[Dict] = None) -> str:
        """Wrap Chinese characters in annotated spans."""
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

    def process_nested_colors(self, text: str) -> str:
        """
        Process nested color tags within parentheses.
        
        :param text: Text that may contain nested color tags
        :return: Processed text with nested color spans
        """
        while True:
            match = self.nested_color_pattern.search(text)
            if not match:
                break

            color = match.group(1)
            inner_text = match.group(2)
            if color in self.COLORS:
                sigil, class_name = self.COLORS[color]
                replacement = (
                    f'<span class="color-{class_name}">'
                    f'(<span class="sigil">{sigil}</span> {inner_text})'
                    f'</span>'
                )
                text = text.replace(match.group(0), replacement)

        return text

    def process_lists(self, text: str) -> str:
        """Convert list markers to HTML lists with appropriate classes."""
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
                
                # Start new list if type changes
                if list_type != current_type:
                    if current_list:
                        processed_lines.append('<ul>')
                        processed_lines.extend(current_list)
                        processed_lines.append('</ul>')
                        current_list = []
                    list_type = current_type
                
                current_list.append(f'<li class="{current_type}">{content}</li>')
            else:
                # Close current list if any
                if current_list:
                    processed_lines.append('<ul>')
                    processed_lines.extend(current_list)
                    processed_lines.append('</ul>')
                    current_list = []
                    list_type = None
                processed_lines.append(line)

        # Close final list if any
        if current_list:
            processed_lines.append('<ul>')
            processed_lines.extend(current_list)
            processed_lines.append('</ul>')

        return '\n'.join(processed_lines)

    def process_urls(self, text: str) -> str:
        """Convert URLs to clickable links."""
        def replacer(match: Match) -> str:
            url = match.group(0)
            sanitized_url = url.replace('"', '%22')  # Escape quotes in URLs
            return f'<a href="{sanitized_url}" target="_blank" rel="noopener noreferrer">{url}</a>'
        return self.url_pattern.sub(replacer, text)

    def process_wikilinks(self, text: str) -> str:
        """Convert [[wikilinks]] to HTML links."""
        def replacer(match: Match) -> str:
            target = match.group(1)
            url = target.replace(' ', '_').replace('"', '%22')
            return f'<a href="https://en.wikipedia.org/wiki/{url}" class="wikilink" target="_blank">{target}</a>'
        return self.wikilink_pattern.sub(replacer, text)

    def process_colors(self, text: str) -> str:
        """Process color tags with sigils."""
        parts = []
        pos = 0
        nested_colors = []

        while pos < len(text):
            start_match = self.color_start_pattern.search(text, pos)
            if not start_match:
                parts.append(text[pos:])
                break

            color = start_match.group(1)
            if color not in self.COLORS:
                pos = start_match.end()
                continue

            # Add text before the tag
            parts.append(text[pos:start_match.start()])
            sigil, class_name = self.COLORS[color]

            # Find matching end tag
            end_pattern = f'</{color}>'
            end_pos = text.find(end_pattern, start_match.end())
            if end_pos == -1:
                pos = start_match.end()
                continue

            # Extract content and process nested colors
            content = text[start_match.end():end_pos]
            
            # Add color span with sigil
            parts.append(f'<span class="color-{class_name}"><span class="sigil">{sigil}</span> {content}</span>')
            
            pos = end_pos + len(end_pattern)

        return ''.join(parts)

    def process_annotations(self, text: str, chinese_annotations: Optional[Dict] = None,
                          llm_annotations: Optional[Dict] = None) -> str:
        """Process Chinese and LLM annotations into hoverable elements."""
        # Process Chinese annotations
        text = self.wrap_chinese(text, chinese_annotations)
        
        # Process LLM annotations (stub)
        if llm_annotations:
            for pos, annotation in llm_annotations.items():
                text = text[:int(pos)] + "🔍✨💡" + text[int(pos):]
        
        return text

    def wrap_paragraphs(self, text: str) -> str:
        """Wrap content in paragraphs where needed."""
        paragraphs = []
        for line in text.split('\n\n'):
            if line.strip():
                line = line.strip()
                # Don't wrap content that's already in a block-level element
                if not (line.startswith('<') and (
                    line.startswith('<p') or 
                    line.startswith('<ul') or 
                    line.startswith('<hr') or
                    line.startswith('<div')
                )):
                    line = f'<p>{line}</p>'
                paragraphs.append(line)
        return '\n'.join(paragraphs)

    def process_content(self, content: str, chinese_annotations: Optional[Dict] = None,
                       llm_annotations: Optional[Dict] = None) -> str:
        """Process text content with all features."""
        if not content:
            return ""

        # First process annotations
        text = self.process_annotations(content, chinese_annotations, llm_annotations)
        
        # Process lists
        text = self.process_lists(text)
        
        # Process URLs and wikilinks
        text = self.process_urls(text)
        text = self.process_wikilinks(text)
        
        # Process nested colors
        text = self.process_nested_colors(text)
        
        # Process color tags
        text = self.process_colors(text)
        
        # Process section breaks
        text = self.section_break_pattern.sub('<hr>', text)
        
        # Sanitize HTML while preserving our tags
        text = self.sanitize_html(text)
        
        # Finally wrap in paragraphs if needed
        text = self.wrap_paragraphs(text)
        
        return text

    def extract_color_content(self, content: str, color: str) -> list[str]:
        """Extract content from specified color tags."""
        pattern = re.compile(f'<{color}>(.*?)</{color}>', re.DOTALL)
        matches = pattern.finditer(content)
        return [match.group(1).strip() for match in matches if match.group(1).strip()]