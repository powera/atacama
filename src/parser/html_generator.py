"""HTML generator for the Atacama message formatting system.

This module provides HTML generation from an Abstract Syntax Tree (AST) created by
the Atacama parser. It handles all node types and formatting features while
maintaining separation between parsing and output generation.
"""

from typing import Dict, Optional, List
from .parser import Node, NodeType, ColorNode, ListItemNode
from .lexer import Token, TokenType
from parser.colorblocks import (
    create_color_block, create_chinese_annotation, create_list_item,
    create_list_container, create_multiline_block, create_literal_text,
    create_url_link, create_wiki_link, create_emphasis
)
from sqlalchemy.orm import Session

import common.chess  # fen_to_board
import common.quotes  # save_quotes
from common.models import Email, Quote

class HTMLGenerator:
    """
    Converts an Atacama AST into formatted HTML following the formal grammar.
    
    This generator creates semantic HTML that preserves the document structure and
    formatting defined by the Atacama markup language. It handles all node types
    defined in the parser, including section breaks, multi-quote blocks, color
    formatting, lists, Chinese text annotations, URLs, wiki-style links, literal
    text, emphasized text, and templates.
    """
    
    def __init__(self, annotations: Optional[Dict] = None, 
                 db_session: Optional[Session] = None,
                 message: Optional[Email] = None):
        """Initialize the HTML generator with optional Chinese text annotations."""
        self.annotations = annotations or {}
        self.db_session = db_session
        self.message = message
        self.in_list = False
        self.current_list_items = []
        self.current_list_type = None

    def generate(self, node: Node) -> str:
        """Generate HTML from an AST node."""
        if not node:
            return ""
            
        method = getattr(self, f'_generate_{node.type.name.lower()}')
        return method(node)
    
    def _generate_document(self, node: Node) -> str:
        """Generate HTML for the root document node."""
        sections = []
        current_section = []
        
        # Track list state
        current_list_items = []
        current_list_type = None
        
        for child in node.children:
            if child.type == NodeType.HR and current_section:
                # End any open list before section break
                if current_list_items:
                    current_section.append(create_list_container(current_list_items))
                    current_list_items = []
                    current_list_type = None
                
                # End current section and start a new one
                sections.append(self._wrap_section(current_section))
                current_section = []
            elif child.type == NodeType.LIST_ITEM:
                item_type = child.marker_type
                item_content = ''.join(self.generate(c) for c in child.children)
                
                if current_list_type is None:
                    # Starting new list
                    current_list_type = item_type
                    current_list_items = [create_list_item(item_content, item_type)]
                elif current_list_type == item_type:
                    # Continue current list
                    current_list_items.append(create_list_item(item_content, item_type))
                else:
                    # Different list type - end current list and start new one
                    current_section.append(create_list_container(current_list_items))
                    current_list_items = [create_list_item(item_content, item_type)]
                    current_list_type = item_type
            else:
                # Non-list content - end any open list
                if current_list_items:
                    current_section.append(create_list_container(current_list_items))
                    current_list_items = []
                    current_list_type = None
                
                content = self.generate(child)
                if content:
                    current_section.append(content)
        
        # Handle any remaining list items
        if current_list_items:
            current_section.append(create_list_container(current_list_items))
        
        # Add final section
        if current_section:
            sections.append(self._wrap_section(current_section))
        
        section_divider = self._generate_hr(None)
        return section_divider.join(sections)
    
    def _wrap_section(self, contents: List[str]) -> str:
        """Wrap a section's contents in a section tag."""
        if not contents:
            return ""
        content = '\n'.join(contents)
        return f'<section class="content-section">\n{content}\n</section>'
    
    def sanitize_html(self, text: str):
        return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

    def _generate_text(self, node: Node) -> str:
        """Generate HTML for plain text content."""
        return self.sanitize_html(node.token.value) if node.token else ''
    
    def _generate_newline(self, node: Node) -> str:
        """Generate HTML for a line break."""
        return '<br />'
    
    def _generate_hr(self, node: Node) -> str:
        """Generate HTML for a horizontal rule (section break)."""
        return '<hr class="section-break" />'
    
    def _generate_mlq(self, node: Node) -> str:
        """Generate HTML for a multi-line quote block."""
        paragraphs = []
        current_paragraph = []
        
        for child in node.children:
            if child.type == NodeType.NEWLINE and current_paragraph:
                paragraphs.append(''.join(current_paragraph))
                current_paragraph = []
            else:
                content = self.generate(child)
                if content:
                    current_paragraph.append(content)
        
        if current_paragraph:
            paragraphs.append(''.join(current_paragraph))
            
        if not paragraphs:
            return ''
            
        return create_multiline_block(paragraphs)
    
    def _generate_color_block(self, node: ColorNode) -> str:
        """Generate HTML for a color-formatted block."""
        content = ''.join(self.generate(child) for child in node.children)

        # Handle quote storage for yellow/quote blocks
        if node.color in ('yellow', 'quote') and content:
            common.quotes.save_quotes(
                [{'text': content.strip(), 'quote_type': 'reference'}], 
                self.message, self.db_session)

        return create_color_block(node.color, content, node.is_line)
    
    def _generate_list_item(self, node: ListItemNode) -> str:
        """Generate HTML for a list item."""
        content = ''.join(self.generate(child) for child in node.children)
        return create_list_item(content, node.marker_type)
    
    def _generate_chinese(self, node: Node) -> str:
        """Generate HTML for Chinese text with annotations."""
        text = node.token.value
        if text in self.annotations:
            ann = self.annotations[text]
            return create_chinese_annotation(
                hanzi=text,
                pinyin=ann["pinyin"],
                definition=ann["definition"]
            )
        return create_chinese_annotation(hanzi=text)
    
    def _generate_url(self, node: Node) -> str:
        """Generate HTML for a URL with proper attributes."""
        return create_url_link(node.token.value)

    def _generate_wikilink(self, node: Node) -> str:
        """Generate HTML for a wiki-style link."""
        title = ''.join(self.generate(child) for child in node.children)
        return create_wiki_link(title)
    
    def _generate_literal(self, node: Node) -> str:
        """Generate HTML for literal text blocks."""
        content = ''.join(self.generate(child) for child in node.children)
        return create_literal_text(content)
    
    def _generate_emphasis(self, node: Node) -> str:
        """Generate HTML for emphasized text."""
        return create_emphasis(node.token.value)
    
    def _generate_template(self, node: Node) -> str:
        """Generate HTML for template blocks."""
        content = node.token.value
        if node.token.type == TokenType.TEMPLATE_PGN:
            return common.chess.fen_to_board(content)
        elif node.token.type == TokenType.TEMPLATE_ISBN:
            return f'<span class="isbn">{content}</span>'
        elif node.token.type == TokenType.TEMPLATE_WIKIDATA:
            return f'<span class="wikidata">{content}</span>'
        return content


def generate_html(ast: Node, annotations: Optional[Dict] = None) -> str:
    """
    Convenience function to generate HTML from an AST.
    
    Args:
        ast: Root node of the AST
        annotations: Optional dictionary of Chinese text annotations
        
    Returns:
        Generated HTML string
    """
    generator = HTMLGenerator(annotations)
    return generator.generate(ast)
