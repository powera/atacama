"""HTML generation functions for Atacama formatting elements."""

import re
from typing import Optional, List, Tuple

# Pre-compiled YouTube URL patterns for performance
# Video IDs are exactly 11 characters: [a-zA-Z0-9_-]{11}
_YOUTUBE_PATTERNS = [
    re.compile(r"(?:https?://)?(?:www\.)?youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})"),
    re.compile(r"(?:https?://)?(?:www\.)?youtu\.be/([a-zA-Z0-9_-]{11})"),
    # Variant with v param not first in query string
    re.compile(r"(?:https?://)?(?:www\.)?youtube\.com/watch\?(?:[^&]*&)*v=([a-zA-Z0-9_-]{11})"),
]

# Color definitions with their sigils and descriptions
# 'TAGNAME': ('SIGIL', 'CSS Class', 'Short description')
COLORS = {
    "xantham": ("🔥", "xantham", "sarcastic, overconfident"),
    "red": ("💡", "red", "forceful, certain"),
    "orange": ("⚔️", "orange", "counterpoint"),
    "yellow": ("💬", "yellow", "quotes"),
    "quote": ("💬", "quote", "quotes"),
    "green": ("⚙️", "green", "technical explanations"),
    "acronym": ("⚙️", "green", "explanations of inline acronyms"),
    "context": ("⚙️", "green", "additional context for a post"),
    "resource": ("⚙️", "green", "a link with additional commentary"),
    "teal": ("🤖", "teal", "LLM output"),
    "blue": ("✨", "blue", "voice from beyond"),
    "violet": ("📣", "violet", "serious"),
    "music": ("🎵", "musicnote", "music note"),
    "mogue": ("🌎", "mogue", "actions taken"),
    "gray": ("💭", "gray", "past stories"),
    "hazel": ("🎭", "hazel", "storytelling"),
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
        # Sanitize content if color is unknown to prevent XSS with content like '<script>...'
        # For known colors, content is assumed to be pre-generated HTML or safe text.
        # However, a general sanitization for 'content' here might be safer if its origin is diverse.
        # For now, matching original behavior: return content as is if color unknown.
        return content

    sigil, class_name, _ = COLORS[color]  # desc is not used here

    # If is_line is False (typically parenthesized), the content is usually already what it needs to be.
    # The original check `if not is_line and not content.startswith('('): content = f"({content})"`
    # was potentially for cases where a color tag was used inline without explicit parentheses in source,
    # but the parser usually creates ColorNode with is_line=True for line-level colors
    # and is_line=False for parenthesized ones where parentheses are part of the parsed structure.
    # Let's assume 'content' is correctly formed by the generator before calling this.
    # If content for a non-line (parenthesized) color block should always be wrapped in literal parens in HTML:
    # if not is_line and not (content.startswith('(') and content.endswith(')')):
    #     content = f"({content})"
    # This might be too aggressive if content is complex HTML. The original check was simpler.
    # Given the AST structure, `content` for `is_line=False` is usually the children of the `ColorNode`
    # which are parsed from within the parentheses, so they don't need extra `()` wrapping here.

    return (
        f"""<span class="colorblock color-{class_name}">"""
        f"""<span class="sigil">{sigil}</span>"""
        f"""<span class="colortext-content">{content}</span>"""
        f"""</span>"""
    )


def create_chinese_annotation(hanzi: str) -> str:
    """
    Generate HTML for annotated Chinese text.

    :param hanzi: Chinese characters
    :return: HTML span with optional data attributes
    """
    # Ensure common.pinyin is importable; consider error handling or type hinting for default_processor
    try:
        from aml_parser import pinyin

        metadata = pinyin.default_processor.get_annotation(hanzi)

        attrs = []
        if metadata is not None and metadata.pinyin:
            attrs.append(f'data-pinyin="{metadata.pinyin}"')
        if metadata is not None and metadata.definition:
            attrs.append(f'data-definition="{metadata.definition}"')

        attr_str = " " + " ".join(attrs) if attrs else ""
        return f'<span class="annotated-chinese"{attr_str}>{hanzi}</span>'
    except ImportError:
        # Fallback if common.pinyin is not available
        return f'<span class="annotated-chinese" data-error="pinyin-module-missing">{hanzi}</span>'
    except Exception:  # pylint: disable=broad-except
        # Fallback for other errors during annotation fetching
        return f'<span class="annotated-chinese" data-error="annotation-failed">{hanzi}</span>'


def create_list_item(content: str, marker_type: str) -> str:
    """
    Generate HTML for a single list item.

    :param content: Item text content (already HTML)
    :param marker_type: 'bullet', 'number', or 'arrow' (CSS class will be f'{marker_type}-list')
    :return: HTML list item string
    """
    return f'<li class="{marker_type}-list">{content}</li>'


def create_list_container(items: List[str]) -> str:
    """
    Wrap list items in a container.

    :param items: List of HTML list item strings (e.g., ["<li>item1</li>", "<li>item2</li>"])
    :return: Complete HTML list (e.g., "<ul>\n<li>item1</li>\n<li>item2</li>\n</ul>")
    """
    if not items:
        return ""
    return f"<ul>\n{chr(10).join(items)}\n</ul>"


def create_multiline_block(paragraphs: List[str], color: Optional[str] = None) -> str:
    """
    Generate HTML for a collapsible multi-line block.

    :param paragraphs: List of paragraph strings (each string is a full paragraph's content, already HTML)
    :param color: Optional color name for styling the MLQ block
    :return: HTML for collapsible block
    """
    # Paragraphs are already processed HTML content for each line/paragraph of MLQ
    content_html = "\n".join(
        f"<p>{p}</p>" for p in paragraphs if p.strip()
    )  # Ensure non-empty paragraphs
    if (
        not content_html and not color
    ):  # Completely empty MLQ without color, maybe return empty or minimal
        # If MLQ must always have its structure, even if empty:
        # content_html = "<p></p>" # or some placeholder
        pass  # Let it generate the structure even if content_html is empty.

    sigil_char = "-"  # Default sigil
    color_class_name = ""

    if color and color in COLORS:
        sigil_char, css_class, _ = COLORS[color]
        color_class_name = f" color-{css_class}"  # Note space for class list

    return (
        f'<div class="mlq{color_class_name}">'
        f'<button type="button" class="mlq-collapse" aria-label="Toggle visibility">'
        f'<span class="mlq-collapse-icon">{sigil_char}</span>'
        f"</button>"
        f'<div class="mlq-content">{content_html}</div>'
        f"</div>"
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
    for pattern in _YOUTUBE_PATTERNS:
        match = pattern.search(url)
        if match:
            return True, match.group(1)
    return False, None


def create_url_link(url: str) -> str:
    """
    Generate HTML for URL, with optional YouTube embed.

    :param url: Full URL
    :return: HTML link with optional YouTube embed container
    """
    # Basic sanitization for the URL in href and display text
    # Browsers are generally good at handling URLs, but minimal encoding for quotes is good.
    # The HTMLGenerator should be providing already sanitized text for display if URL itself is token value.
    # If URL is from a text node which has already been sanitized, then url might contain &amp; etc.
    # Assuming 'url' parameter is the raw URL string.

    sanitized_url_for_href = url.replace('"', "%22").replace("'", "%27")  # Basic href safety
    # For display, browsers handle most characters in URLs well.
    # If it needs strict HTML character encoding:
    # display_url = html.escape(url)
    display_url = url  # Typically, URLs are displayed as they are.

    base_link = (
        f'<a href="{sanitized_url_for_href}" target="_blank" '
        f'rel="noopener noreferrer">{display_url}</a>'
    )

    is_youtube, video_id = _detect_youtube_url(url)
    if is_youtube and video_id:
        # The youtube-embed-container structure seems designed for specific JS handling
        return (
            f"{base_link}"
            f'<span class="colorblock youtube-embed-container">'  # Uses 'colorblock' class
            f'<span class="sigil">📺</span>'
            f'<span class="colortext-content">'  # Content is usually hidden/shown by JS
            f'<span class="youtube-player" data-video-id="{video_id}"></span>'
            f"</span>"
            f"</span>"
        )

    return base_link


def create_wiki_link(title: str) -> str:
    """
    Generate HTML for wiki link.
    'title' is the already processed content from child nodes of WIKILINK.

    :param title: Page title (can be HTML if WIKILINK contained formatted text)
    :return: HTML link to Wikipedia
    """
    # The title can be complex HTML if the wikilink source was e.g. [[ *Foo* Bar ]].
    # For the URL, we need a plain text representation.
    # This requires stripping HTML tags from 'title' for URL generation.
    # A simple regex for stripping tags (not foolproof for complex HTML):
    plain_title_for_url = re.sub(r"<[^>]+>", "", title).strip()

    # URL encode the plain title
    # Python's urllib.parse.quote_plus would be robust here.
    # Simplified version:
    url_encoded_title = plain_title_for_url.replace(" ", "_").replace('"', "%22")

    return (
        f'<a href="https://en.wikipedia.org/wiki/{url_encoded_title}" '
        f'class="wikilink" target="_blank">{title}</a>'
    )  # Display original 'title' (can be HTML)


def create_emphasis(content: str) -> str:
    """
    Generate HTML for emphasized text.
    'content' is the raw text between asterisks from the EMPHASIS token.
    It should be sanitized.

    :param content: Text to emphasize (raw string from token)
    :return: HTML with em tag
    """
    # Assuming content is plain text and needs sanitization
    from html import escape  # Proper HTML escaping

    return f"<em>{escape(content)}</em>"


def create_inline_title(content: str) -> str:
    """
    Generate HTML for an inline title tag.
    'content' is already processed HTML from children nodes.

    :param content: Content of the title (already HTML)
    :return: HTML span for inline title
    """
    return f'<span class="inline-title">{content}</span>'


def create_template_html(template_name: Optional[str], content: str) -> str:
    """
    Generate HTML for simple templates like isbn, wikidata.
    'content' is the raw string from the template token.

    :param template_name: Name of the template (e.g., "isbn", "wikidata")
    :param content: Raw content string from the template token
    :return: HTML string for the template, or sanitized content if template unknown
    """
    from html import escape  # Proper HTML escaping for content

    sanitized_content = escape(content)

    if template_name == "isbn":
        return f'<span class="isbn">{sanitized_content}</span>'
    elif template_name == "wikidata":
        # Wikidata content might be an ID, usually safe, but sanitize for consistency.
        return f'<span class="wikidata">{sanitized_content}</span>'
    # Default fallback: return the sanitized content if template name is unknown or None
    return sanitized_content
