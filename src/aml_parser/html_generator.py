"""HTML generator for the Atacama message formatting system.

This module provides HTML generation from an Abstract Syntax Tree (AST) created by
the Atacama parser. It handles all node types and formatting features while
maintaining separation between parsing and output generation.
"""

from typing import Any, Optional, List
from aml_parser.parser import Node, NodeType, ColorNode, ListItemNode
from aml_parser.colorblocks import (
    create_color_block,
    create_chinese_annotation,
    create_list_item,
    create_list_container,
    create_multiline_block,
    create_literal_text,
    create_url_link,
    create_wiki_link,
    create_emphasis,
    create_inline_title,
    create_template_html,
)

from aml_parser.chess import fen_to_board


class ParagraphAggregator:
    """Collects inline content and flushes to paragraph HTML."""

    def __init__(self):
        self._parts: List[str] = []

    def add(self, content: str) -> None:
        """Add inline content to the current paragraph."""
        if content:
            self._parts.append(content)

    def has_content(self) -> bool:
        """Check if there's any content in the current paragraph."""
        return bool(self._parts)

    def flush(self) -> str:
        """Flush the current paragraph and return HTML."""
        if not self._parts:
            return ""
        content = "".join(self._parts)
        self._parts = []
        if not content.strip():
            return ""
        return f"<p>{content}</p>"


class ListAggregator:
    """Collects list items and flushes to list HTML."""

    def __init__(self):
        self._items: List[str] = []
        self._marker_type: Optional[str] = None

    def add(self, item_html: str, marker_type: str) -> str:
        """Add a list item. Returns HTML to flush if marker type changed."""
        flushed = ""
        if self._marker_type is not None and self._marker_type != marker_type:
            flushed = self.flush()
        self._marker_type = marker_type
        self._items.append(item_html)
        return flushed

    def has_content(self) -> bool:
        """Check if there are any list items."""
        return bool(self._items)

    def flush(self) -> str:
        """Flush the current list and return HTML."""
        if not self._items:
            return ""
        html = create_list_container(self._items)
        self._items = []
        self._marker_type = None
        return html


class HTMLGenerator:
    """
    Converts an Atacama AST into formatted HTML following the formal grammar.

    This generator creates semantic HTML that preserves the document structure and
    formatting defined by the Atacama markup language. It handles all node types
    defined in the parser, including section breaks, multi-quote blocks, color
    formatting, lists, Chinese text annotations, URLs, wiki-style links, literal
    text, emphasized text, and templates.
    """

    def __init__(
        self,
        db_session: Optional[Any] = None,
        message: Optional[Any] = None,
        truncated: Optional[bool] = False,
    ):
        """Initialize the HTML generator.

        Args:
            db_session: Optional SQLAlchemy session for quote saving (quote feature only)
            message: Optional Email model instance for quote saving (quote feature only)
            truncated: Whether to truncate output at --MORE-- tags
        """
        self.db_session = db_session
        self.message = message
        self.truncated = truncated

    def generate(self, node: Node) -> str:
        """Generate HTML from an AST node."""
        if not node:
            return ""

        method_name = f"_generate_{node.type.name.lower()}"
        method = getattr(
            self, method_name, self._generate_unknown
        )  # Added fallback for unknown types
        return method(node)

    def _generate_unknown(self, node: Node) -> str:
        """Fallback for unknown node types, treating as text if possible."""
        if node.token and node.token.value:
            return self.sanitize_html(node.token.value)
        return ""

    def _generate_document(self, node: Node) -> str:
        """Generate HTML for the root document node."""
        segments: List[str] = []
        paragraph = ParagraphAggregator()
        list_items = ListAggregator()

        def flush_all() -> None:
            """Flush both paragraph and list to segments."""
            p_html = paragraph.flush()
            if p_html:
                segments.append(p_html)
            l_html = list_items.flush()
            if l_html:
                segments.append(l_html)

        def flush_paragraph_only() -> None:
            """Flush paragraph to segments."""
            p_html = paragraph.flush()
            if p_html:
                segments.append(p_html)

        def flush_list_only() -> None:
            """Flush list to segments."""
            l_html = list_items.flush()
            if l_html:
                segments.append(l_html)

        for child_node in node.children:
            if child_node.type == NodeType.HR:
                flush_all()
                segments.append(self.generate(child_node))

            elif child_node.type == NodeType.MORE_TAG:
                flush_all()
                if self.truncated:
                    segments.append('<p class="readmore">Click title to read full message...</p>')
                    break
                else:
                    segments.append(
                        '<div class="content-sigil" aria-label="Extended content begins here">&#9135;&#9135;&#9135;&#9135;&#9135;</div>'
                    )

            elif child_node.type == NodeType.LIST_ITEM and isinstance(child_node, ListItemNode):
                flush_paragraph_only()
                item_content_html = "".join(self.generate(c) for c in child_node.children)
                flushed = list_items.add(
                    create_list_item(item_content_html, child_node.marker_type),
                    child_node.marker_type,
                )
                if flushed:
                    segments.append(flushed)

            elif child_node.type == NodeType.NEWLINE:
                flush_paragraph_only()

            else:
                # Any non-list item ends the current list
                flush_list_only()
                generated_content = self.generate(child_node)

                # Block-level elements go directly to segments
                if child_node.type == NodeType.MLQ:
                    flush_paragraph_only()
                    if generated_content:
                        segments.append(generated_content)
                elif generated_content:
                    # Inline content goes to current paragraph
                    paragraph.add(generated_content)

        # Flush any remaining content
        flush_all()

        return "\n".join(segments)

    def _wrap_section(self, contents: List[str]) -> str:
        """Wrap a section's contents in a section tag (currently a no-op for the tag itself)."""
        if not contents:
            return ""
        content = "\n".join(contents)
        # return f'<section class="content-section">\n{content}\n</section>' # Original was commented out
        return content

    def sanitize_html(self, text: str):
        return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    def _generate_text(self, node: Node) -> str:
        """Generate HTML for plain text content."""
        if not node.token:
            return ""
        # If a TEXT node has children, it's likely from constructs like resolved parentheses
        # e.g. TEXT(token='(', children=[Node(TEXT, token='content'), Node(TEXT, token=')')])
        if node.children:
            content_parts = []
            if node.token.value:  # Ensure token value itself is added if present
                content_parts.append(self.sanitize_html(node.token.value))
            for child in node.children:
                child_html = self.generate(child)
                if child_html:
                    content_parts.append(child_html)
            return "".join(content_parts)
        return self.sanitize_html(node.token.value)

    def _generate_newline(self, node: Node) -> str:
        """Generate HTML for a line break."""
        return "<br />"

    def _generate_hr(self, node: Node) -> str:
        """Generate HTML for a horizontal rule (section break)."""
        return '<hr class="section-break" />'

    def _generate_more_tag(self, node: Node) -> str:
        """
        Generate HTML for a MORE_TAG node.

        This is primarily handled in _generate_document for structural flow control,
        but this method can be called directly if needed.
        """
        if self.truncated:
            return '<p class="readmore">Click title to read full message...</p>'
        else:
            return '<div class="content-sigil" aria-label="Extended content begins here">&#9135;&#9135;&#9135;&#9135;&#9135;</div>'

    def _generate_mlq(self, node: Node) -> str:
        """Generate HTML for a multi-line quote block."""
        paragraphs: List[str] = []
        current_paragraph_parts: List[str] = []

        for child in node.children:
            # Check if child is a NEWLINE separating paragraphs within MLQ
            if child.type == NodeType.NEWLINE:
                if current_paragraph_parts:  # Finalize current paragraph
                    paragraphs.append("".join(current_paragraph_parts))
                    current_paragraph_parts = []
            else:
                content = self.generate(child)
                if content:
                    current_paragraph_parts.append(content)

        if current_paragraph_parts:  # Add last paragraph
            paragraphs.append("".join(current_paragraph_parts))

        if not paragraphs:  # Handle empty MLQ, e.g. "<<< >>>"
            # Check if node has a color attribute (for "<<< <red> >>>" which is unusual but to consider)
            # For an empty MLQ, create_multiline_block might still produce the structure.
            # If the parser ensures non-empty content for MLQ children or handles empty MLQs,
            # this 'if not paragraphs' might be less critical.
            pass  # create_multiline_block will handle an empty list of paragraphs if needed

        return create_multiline_block(paragraphs, getattr(node, "color", None))

    def _generate_color_block(self, node: ColorNode) -> str:
        """Generate HTML for a color-formatted block."""
        content = "".join(self.generate(child) for child in node.children)

        # Quote saving feature - imports are local to avoid requiring SQLAlchemy
        # for basic parsing functionality
        if node.color in ("yellow", "quote") and content and self.db_session and self.message:
            from models.quotes import save_quotes

            save_quotes(
                [{"text": content.strip(), "quote_type": "reference"}],
                self.message,
                self.db_session,
            )

        return create_color_block(node.color, content, node.is_line)

    def _generate_list_item(self, node: ListItemNode) -> str:
        """
        Generate HTML for a list item's content.
        The actual <li> tag is created by create_list_item in colorblocks.py,
        called from _generate_document. This method should ideally not be called directly
        by the main dispatch if _generate_document handles LIST_ITEM nodes specially.
        However, if it were called, it would generate the inner content.
        """
        # This method is somewhat redundant if _generate_document handles LIST_ITEM nodes
        # by directly processing their children and marker_type.
        # For robustness, if called, it should generate the content of the list item.
        return "".join(self.generate(child) for child in node.children)

    def _generate_chinese(self, node: Node) -> str:
        """Generate HTML for Chinese text with annotations."""
        if not node.token or not node.token.value:
            return ""
        return create_chinese_annotation(hanzi=node.token.value)

    def _generate_url(self, node: Node) -> str:
        """Generate HTML for a URL with proper attributes."""
        if not node.token or not node.token.value:
            return ""
        return create_url_link(node.token.value)

    def _generate_wikilink(self, node: Node) -> str:
        """Generate HTML for a wiki-style link."""
        title = "".join(self.generate(child) for child in node.children)
        return create_wiki_link(title)

    def _generate_literal(self, node: Node) -> str:
        """Generate HTML for literal text blocks."""
        content = "".join(self.generate(child) for child in node.children)
        return create_literal_text(content)

    def _generate_emphasis(self, node: Node) -> str:
        """Generate HTML for emphasized text."""
        if not node.token or not node.token.value:
            return ""
        return create_emphasis(node.token.value)

    def _generate_title(self, node: Node) -> str:
        """Generate HTML for an inline title tag."""
        content = "".join(self.generate(child) for child in node.children)
        return create_inline_title(content)  # Uses function from colorblocks

    def _generate_template(self, node: Node) -> str:
        """Generate HTML for template blocks."""
        if not node.token:
            return ""
        content = node.token.value
        template_name = node.token.template_name

        if template_name == "pgn":
            return fen_to_board(content)
        # Delegate other known templates to colorblocks
        # Ensure content is passed, as create_template_html expects it.
        # If template_name is None or not handled by create_template_html, it returns content.
        return create_template_html(template_name, content)


def generate_html(ast: Node, **kwargs) -> str:
    """
    Convenience function to generate HTML from an AST.

    Args:
        ast: Root node of the AST
        **kwargs: Arguments to pass to HTMLGenerator constructor (db_session, message, truncated)

    Returns:
        Generated HTML string
    """
    generator = HTMLGenerator(**kwargs)
    return generator.generate(ast)
