import re
from typing import Dict, Pattern, Tuple, Optional, Match
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
        # Pattern for color tags at start of line
        self.para_patterns: Dict[str, Pattern] = {
            color: re.compile(f'^[ \t]*<{color}>(.*?)$', re.MULTILINE | re.DOTALL)
            for color in self.COLORS.keys()
        }
        
        # Pattern for all color tags
        self.all_patterns: Dict[str, Pattern] = {
            color: re.compile(f'<{color}>(.*?)$', re.DOTALL)
            for color in self.COLORS.keys()
        }
        
        # Pattern for section breaks
        self.section_break_pattern = re.compile(r'^[ \t]*----[ \t]*\r?\n', re.MULTILINE)
        
        # Pattern for URLs
        self.url_pattern = re.compile(
            r'https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+[^\s]*'
        )
        
        # Pattern for nested colors using parentheses
        self.nested_color_pattern = re.compile(
            r'\([ \t]*<(\w+)>(.*?)[ \t]*\)'
        )
        
        # New patterns for lists and wikilinks
        self.list_pattern = re.compile(r'^[ \t]*<<[ \t]*([*#>])[ \t]*(.+?)[ \t]*>>[ \t]*$', re.MULTILINE)
        self.wikilink_pattern = re.compile(r'\[\[([^]]+)\]\]')
        
        # Pattern for Chinese characters with potential annotations
        self.chinese_pattern = re.compile(r'[\u4e00-\u9fff]+')

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
        
        # Restore approved HTML tags used by our processor
        approved_tags = ['p', 'span', 'hr', 'li', 'ul', 'ol', 'a']
        for tag in approved_tags:
            text = text.replace(f'&lt;{tag}', f'<{tag}')
            text = text.replace(f'&lt;/{tag}&gt;', f'</{tag}>')
            
        # Restore class attributes
        text = text.replace('&lt;p class=', '<p class=')
        text = text.replace('&lt;span class=', '<span class=')
        
        return text

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

    def extract_color_content(self, content: str, color: str) -> list[str]:
        """
        Extract content wrapped in specified color tags.
        
        :param content: Text content to process
        :param color: Color tag name to extract (e.g. 'yellow', 'blue')
        :return: List of text content found within the specified color tags
        """
        # Create pattern for both inline and paragraph color tags
        pattern = re.compile(
            f'<{color}>(.*?)(?:\r?\n|$)',  # Matches till newline or end of string
            re.MULTILINE | re.DOTALL
        )
        
        # Find all matches and extract content
        matches = pattern.finditer(content)
        extracted = [match.group(1).strip() for match in matches]
        
        return [text for text in extracted if text]  # Filter out empty strings

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
        
        # First replace individual items
        processed = self.list_pattern.sub(replace_list, text)
        
        # Then wrap consecutive items in appropriate list tags
        # (This is a simplified version - we might want more sophisticated list nesting)
        processed = re.sub(
            r'(<li class="bullet-list">.*?</li>)\n+(?=<li class="bullet-list">)',
            r'\1',
            processed,
            flags=re.DOTALL
        )
        processed = re.sub(
            r'(<li class="number-list">.*?</li>)\n+(?=<li class="number-list">)',
            r'\1',
            processed,
            flags=re.DOTALL
        )
        processed = re.sub(
            r'(<li class="arrow-list">.*?</li>)\n+(?=<li class="arrow-list">)',
            r'\1',
            processed,
            flags=re.DOTALL
        )
        
        return processed

    def process_wikilinks(self, text: str, base_url: str = "https://en.wikipedia.org/wiki/") -> str:
        """Convert [[wikilinks]] to HTML links."""
        def replace_link(match: Match) -> str:
            target = match.group(1)
            url = base_url + target.replace(' ', '_')
            return f'<a href="{url}" class="wikilink" target="_blank">{target}</a>'
            
        return self.wikilink_pattern.sub(replace_link, text)

    def process_annotations(self, text: str, chinese_annotations: Optional[Dict] = None, 
                          llm_annotations: Optional[Dict] = None) -> str:
        """Process Chinese and LLM annotations into hoverable elements."""
        if chinese_annotations:
            def add_chinese_annotation(match: Match) -> str:
                hanzi = match.group(0)
                if hanzi in chinese_annotations:
                    ann = chinese_annotations[hanzi]
                    return (f'<span class="annotated-chinese" '
                           f'data-pinyin="{ann["pinyin"]}" '
                           f'data-definition="{ann["definition"]}">'
                           f'{hanzi}</span>')
                return hanzi
            
            text = self.chinese_pattern.sub(add_chinese_annotation, text)
        
        if llm_annotations:
            # Insert LLM annotations at specified positions
            # This needs to account for HTML tags we've already inserted
            # A more robust solution might use a proper HTML parser
            for pos, annotation in sorted(llm_annotations.items(), reverse=True):
                text = (text[:pos] + 
                       f'<span class="llm-annotation" data-type="{annotation["type"]}">'
                       f'{annotation["content"]}</span>' +
                       text[pos:])
        
        return text

    def process_content(self, content: str, chinese_annotations: Optional[Dict] = None,
                       llm_annotations: Optional[Dict] = None) -> str:
        """Process text content and wrap color tags in HTML/CSS with sigils."""
        # First process annotations (before any HTML escaping)
        processed = self.process_annotations(content, chinese_annotations, llm_annotations)
        
        # Process lists
        processed = self.process_lists(processed)
        
        # Sanitize HTML (but preserve our processed tags)
        processed = self.sanitize_html(processed)
        
        # Process URLs
        processed = self.process_urls(processed)
        # Then process wikilinks
        processed = self.process_wikilinks(processed)
        
        # Process nested colors
        processed = self.process_nested_colors(processed)
        
        # Process paragraph-starting color tags
        for color, (sigil, class_name) in self.COLORS.items():
            matches = self.para_patterns[color].finditer(processed)
            for match in matches:
                text = match.group(1)
                replacement = f'<p class="color-{class_name}"><span class="sigil">{sigil}</span> {text}</p>'
                processed = processed.replace(match.group(0), replacement)
        
        # Process remaining (inline) color tags
        for color, (sigil, class_name) in self.COLORS.items():
            all_matches = list(self.all_patterns[color].finditer(processed))
            para_matches = list(self.para_patterns[color].finditer(content))
            
            for match in all_matches:
                if not any(pm.start() == match.start() for pm in para_matches):
                    text = match.group(1)
                    replacement = f'<span class="color-{class_name}"><span class="sigil">{sigil}</span> {text}</span>'
                    processed = processed.replace(match.group(0), replacement)
        
        # Process section breaks
        processed = self.section_break_pattern.sub('<hr>\n', processed)
        
        # Process paragraphs
        paragraphs = re.split(r'\n+', processed)
        processed_paragraphs = []
        
        for para in paragraphs:
            if not para.strip():
                continue
            if para.strip().startswith('<') and para.strip().endswith('>'):
                processed_paragraphs.append(para)
            else:
                processed_paragraphs.append(f'<p>{para.strip()}</p>')
        
        return '\n'.join(processed_paragraphs)
