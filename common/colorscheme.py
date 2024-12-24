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
            color: re.compile(f'<{color}>(.*?)(?=<|$)', re.DOTALL)
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
        
        # Pattern for lists (updated for better matching)
        self.list_pattern = re.compile(
            r'^[ \t]*(?:<<[ \t]*([*#>])[ \t]*(.+?)[ \t]*>>|[-*][ \t]+(.+?))[ \t]*$',
            re.MULTILINE
        )
        self.list_block_pattern = re.compile(
            r'((?:^[ \t]*(?:<<[ \t]*[*#>][ \t]*|[-*][ \t]+).+?[ \t]*(?:>>)?[ \t]*$\n?)+)',
            re.MULTILINE
        )
        
        # Pattern for wikilinks
        self.wikilink_pattern = re.compile(r'\[\[([^]]+)\]\]')
        
        # Pattern for Chinese characters with potential annotations
        self.chinese_pattern = re.compile(r'[\u4e00-\u9fff]+')
        
        # Pattern for paragraphs and line breaks
        self.paragraph_pattern = re.compile(r'\n\n+')
        self.linebreak_pattern = re.compile(r'\n')

    def sanitize_html(self, text: str) -> str:
        """
        Basic HTML sanitization to prevent XSS while preserving custom tags.
        
        :param text: Text to sanitize
        :return: Sanitized text
        """
        # First escape any existing HTML
        text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        
        # Then restore our custom color tags
        for color in self.COLORS.keys():
            text = text.replace(f'&lt;{color}&gt;', f'<{color}>')
        
        # Restore approved HTML tags used by our processor
        approved_tags = ['p', 'span', 'hr', 'li', 'ul', 'ol', 'a', 'br', 'div']
        for tag in approved_tags:
            text = text.replace(f'&lt;{tag}', f'<{tag}')
            text = text.replace(f'&lt;/{tag}&gt;', f'</{tag}>')
            
        # Restore class attributes
        text = text.replace('&lt;p class=', '<p class=')
        text = text.replace('&lt;span class=', '<span class=')
        text = text.replace('&lt;div class=', '<div class=')
        
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
            return f'<a href="{url}" target="_blank" rel="noopener noreferrer">{url}</a>'
            
        return self.url_pattern.sub(replace_url, text)

    def process_lists(self, text: str) -> str:
        """
        Process list markers and create HTML lists.
        
        :param text: Text that may contain list items
        :return: Processed text with HTML lists
        """
        def process_list_block(match: Match) -> str:
            block = match.group(1)
            lines = block.strip().split('\n')
            
            # Determine list type from first item
            first_line = lines[0]
            list_type = 'ul'
            list_class = 'bullet-list'
            
            if '<<#' in first_line:
                list_type = 'ol'
                list_class = 'number-list'
            elif '<<>' in first_line:
                list_class = 'arrow-list'
            
            # Process individual items
            items = []
            for line in lines:
                # Handle both << >> syntax and standard markdown
                content = ''
                if '<<' in line:
                    marker_match = self.list_pattern.match(line)
                    if marker_match:
                        content = marker_match.group(2) or marker_match.group(3)
                else:
                    marker_match = self.list_pattern.match(line)
                    if marker_match:
                        content = marker_match.group(3)
                
                if content:
                    items.append(f'<li class="{list_class}">{content}</li>')
            
            return f'<{list_type} class="list-container">\n{"".join(items)}\n</{list_type}>'
        
        # Process list blocks
        return self.list_block_pattern.sub(process_list_block, text)

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
            # Create a list of (position, tag) tuples
            annotations = []
            for pos, annotation in llm_annotations.items():
                pos = int(pos)  # Ensure position is an integer
                start_tag = f'<span class="llm-annotation" data-type="{annotation["type"]}">'
                end_tag = '</span>'
                annotations.append((pos, start_tag))
                annotations.append((pos + len(annotation["content"]), end_tag))
            
            # Sort annotations by position in reverse order
            annotations.sort(reverse=True)
            
            # Insert tags
            for pos, tag in annotations:
                text = text[:pos] + tag + text[pos:]
        
        return text

    def process_paragraphs(self, text: str) -> str:
        """
        Process text into proper paragraphs and handle line breaks.
        
        :param text: Raw text content
        :return: Text with HTML paragraphs and line breaks
        """
        # First split into paragraphs
        paragraphs = self.paragraph_pattern.split(text)
        
        # Process each paragraph
        processed_paragraphs = []
        for para in paragraphs:
            if not para.strip():
                continue
                
            # Handle line breaks within paragraphs
            para = self.linebreak_pattern.sub('<br>\n', para.strip())
            
            # Don't wrap already-wrapped content
            if not (para.startswith('<p') or para.startswith('<div') or 
                   para.startswith('<ul') or para.startswith('<ol')):
                para = f'<p>{para}</p>'
                
            processed_paragraphs.append(para)
        
        return '\n\n'.join(processed_paragraphs)

    def process_content(self, content: str, chinese_annotations: Optional[Dict] = None,
                       llm_annotations: Optional[Dict] = None) -> str:
        """Process text content and wrap color tags in HTML/CSS with sigils."""
        if not content:
            return ""
            
        # First process annotations (before any HTML escaping)
        processed = self.process_annotations(content, chinese_annotations, llm_annotations)
        
        # Process lists (before general HTML processing)
        processed = self.process_lists(processed)
        
        # Sanitize HTML (but preserve our processed tags)
        processed = self.sanitize_html(processed)
        
        # Process URLs and wikilinks
        processed = self.process_urls(processed)
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
            matches = self.all_patterns[color].finditer(processed)
            for match in matches:
                text = match.group(1)
                replacement = f'<span class="color-{class_name}"><span class="sigil">{sigil}</span> {text}</span>'
                processed = processed.replace(match.group(0), replacement)
        
        # Process section breaks
        processed = self.section_break_pattern.sub('<hr>\n', processed)
        
        # Finally, process paragraphs and line breaks
        processed = self.process_paragraphs(processed)
        
        return processed

    def extract_color_content(self, content: str, color: str) -> list[str]:
        """
        Extract content wrapped in specified color tags.
        
        :param content: Text content to process
        :param color: Color tag name to extract (e.g. 'yellow', 'blue')
        :return: List of text content found within the specified color tags
        """
        # Create pattern for both inline and paragraph color tags
        pattern = re.compile(
            f'<{color}>(.*?)(?=<|$)',  # Matches till next tag or end of string
            re.MULTILINE | re.DOTALL
        )
        
        # Find all matches and extract content
        matches = pattern.finditer(content)
        extracted = [match.group(1).strip() for match in matches]
        
        return [text for text in extracted if text]  # Filter out empty strings
