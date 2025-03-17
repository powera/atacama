"""HTML generation functions for Atacama formatting elements."""

import re
from typing import Dict, Optional, List, Tuple

# Color definitions with their sigils and descriptions
# 'TAGNAME': ('SIGIL', 'CSS Class', 'Short description')
COLORS = {
    'xantham': ('🔥', 'xantham', 'sarcastic, overconfident'),
    'red': ('💡', 'red', 'forceful, certain'),
    'orange': ('⚔️', 'orange', 'counterpoint'),
    'yellow': ('💬', 'yellow', 'quotes'),
    'quote': ('💬', 'quote', 'quotes'),
    'green': ('⚙️', 'green', 'technical explanations'),
    'acronym': ('⚙️', 'green', 'explanations of inline acronyms'),
    'context': ('⚙️', 'green', 'additional context for a post'),
    'resource': ('⚙️', 'green', 'a link with additional commentary'),
    'teal': ('🤖', 'teal', 'LLM output'),
    'blue': ('✨', 'blue', 'voice from beyond'),
    'violet': ('📣', 'violet', 'serious'),
    'music': ('🎵', 'musicnote', 'music note'),
    'mogue': ('🌎', 'mogue', 'actions taken'),
    'gray': ('💭', 'gray', 'past stories'),
    'hazel': ('🎭', 'hazel', 'storytelling'),
}

def create_color_block(color: str, content: str, is_line: bool = False) -> str:
    """
    Generate HTML for a color-formatted block.
    
    :param color: Color name (must be in COLORS dict)
    :param content: Text content to wrap
    :param is_line: True for line-level formatting, False for inline/parenthesized
    :return: Formatted HTML string
    """
    if color not in COLORS:
        return content
        
    sigil, class_name, desc = COLORS[color]
    
    # Handle nested colors (with parentheses) vs line-level colors
    if not is_line and not content.startswith('('):  # )
        content = f"({content})"
        
    return (
        f'''<span class="colorblock color-{class_name}">
    <span class="sigil">{sigil}</span>
    <span class="colortext-content">{content}</span>
  </span>'''
    )

def create_chinese_annotation(hanzi: str) -> str:
    """
    Generate HTML for annotated Chinese text.
    
    :param hanzi: Chinese characters
    :return: HTML span with optional data attributes
    """
    import common.pinyin
    metadata = common.pinyin.default_processor.get_annotation(hanzi)
    
    attrs = []
    if metadata.pinyin:
        attrs.append(f'data-pinyin="{metadata.pinyin}"')
    if metadata.definition:
        attrs.append(f'data-definition="{metadata.definition}"')
        
    attr_str = ' ' + ' '.join(attrs) if attrs else ''
    return f'<span class="annotated-chinese"{attr_str}>{hanzi}</span>'

def create_list_item(content: str, marker_type: str) -> str:
    """
    Generate HTML for a single list item.
    
    :param content: Item text content
    :param marker_type: 'bullet', 'number', or 'arrow'
    :return: HTML list item
    """
    return f'<li class="{marker_type}-list">{content}</li>'

def create_list_container(items: List[str]) -> str:
    """
    Wrap list items in a container.
    
    :param items: List of HTML list item strings
    :return: Complete HTML list
    """
    return f'<ul>\n{chr(10).join(items)}\n</ul>'

def create_multiline_block(paragraphs: List[str], color=None) -> str:
    """
    Generate HTML for a collapsible multi-line block.
    
    :param paragraphs: List of paragraph strings
    :return: HTML for collapsible block
    """
    content_html = '\n'.join(f'<p>{p}</p>' for p in paragraphs)
   
    if color:
        sigil, class_name, desc = COLORS[color]
        color_div = f" color-{class_name}"
    else:
        color_div = ""
        sigil = "-"
    return (
        f'<div class="mlq{color_div}">'
        f'<button type="button" class="mlq-collapse" aria-label="Toggle visibility">'
        f'<span class="mlq-collapse-icon">{sigil}</span>'
        f'</button>'
        f'<div class="mlq-content">{content_html}</div>'
        f'</div>'
    )

def create_literal_text(content: str) -> str:
    """
    Generate HTML for literal text block.
    
    :param content: Text content
    :return: HTML span with literal-text class
    """
    return f'<span class="literal-text">{content.strip()}</span>'

def _detect_youtube_url(url: str) -> Tuple[bool, Optional[str]]:
    """
    Check if URL is a Youtube video and extract video ID.
    
    :param url: URL to check
    :return: Tuple of (is_youtube, video_id)
    """
    youtube_patterns = [
        r'(?:https?:\/\/)?(?:www\.)?youtube\.com\/watch\?v=([a-zA-Z0-9_-]+)',
        r'(?:https?:\/\/)?(?:www\.)?youtu\.be\/([a-zA-Z0-9_-]+)'
    ]

    for pattern in youtube_patterns:
        match = re.match(pattern, url)
        if match:
            return True, match.group(1)
    return False, None

def create_url_link(url: str) -> str:
    """
    Generate HTML for URL, with optional YouTube embed.
    
    :param url: Full URL
    :return: HTML link with optional YouTube embed container
    """
    sanitized_url = url.replace('"', '%22')
    base_link = (f'<a href="{sanitized_url}" target="_blank" '
                f'rel="noopener noreferrer">{url}</a>')
    
    # Check for YouTube URL
    is_youtube, video_id = _detect_youtube_url(url)
    if is_youtube and video_id:
        return (
            f'{base_link}'
            f'<span class="colorblock youtube-embed-container">'
            f'<span class="sigil">📺</span>'
            f'<span class="colortext-content">'
            f'<span class="youtube-player" data-video-id="{video_id}"></span>'
            f'</span>'
            f'</span>'
        )
    
    return base_link

def create_wiki_link(title: str) -> str:
    """
    Generate HTML for wiki link.
    
    :param title: Page title
    :return: HTML link to Wikipedia
    """
    url = title.replace(' ', '_').replace('"', '%22')
    return (f'<a href="https://en.wikipedia.org/wiki/{url}" '
            f'class="wikilink" target="_blank">{title}</a>')

def create_emphasis(content: str) -> str:
    """
    Generate HTML for emphasized text.
    
    :param content: Text to emphasize
    :return: HTML with em tag
    """
    return f'<em>{content}</em>'
