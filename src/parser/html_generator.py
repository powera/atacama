from typing import Dict, Optional, List
from .parser import Node, NodeType, ColorNode
from common.colorblocks import (
    create_color_block, create_chinese_annotation, create_list_item,
    create_list_container, create_multiline_block, create_literal_text,
    create_url_link, create_wiki_link, create_emphasis
)

class HTMLGenerator:
    """
    Converts an Atacama AST into formatted HTML following the formal grammar.
    
    This generator creates semantic HTML that preserves the document structure and
    formatting defined by the Atacama markup language. It properly handles the
    priority ordering of formatting elements, with section breaks as the highest
    priority and multi-quote blocks as the second highest.
    """
    
    def __init__(self, annotations: Optional[Dict] = None):
        """Initialize the HTML generator with optional Chinese text annotations."""
        self.annotations = annotations or {}
    
    def generate(self, node: Node) -> str:
        """Generate HTML from an AST node."""
        if not node:
            return ""
            
        method = getattr(self, f'_generate_{node.type.name.lower()}')
        return method(node)
    
    def _generate_document(self, node: Node) -> str:
        """Generate HTML for the root document node."""
        return '\n'.join(self.generate(child) for child in node.children)
    
    def _generate_section(self, node: Node) -> str:
        """Generate HTML for a section (content between section breaks)."""
        content = '\n'.join(self.generate(child) for child in node.children)
        return f'<section class="content-section">\n{content}\n</section>'
    
    def _generate_multi_quote(self, node: Node) -> str:
        """Generate HTML for a multi-paragraph quote block."""
        paragraphs = [self.generate(child) for child in node.children]
        return create_multiline_block(paragraphs)
    
    def _generate_paragraph(self, node: Node) -> str:
        """Generate HTML for a paragraph node."""
        content = ''.join(self.generate(child) for child in node.children)
        if not content.strip():
            return ""
        if not content.startswith('<'):  # Don't wrap already-wrapped content
            return f'<p>{content}</p>'
        return content
    
    def _generate_list(self, node: Node) -> str:
        """Generate HTML for a list structure."""
        items = []
        for child in node.children:
            item_content = self.generate(child)
            items.append(create_list_item(item_content, node.marker_type))
            
        return create_list_container(items)
    
    def _generate_list_item(self, node: Node) -> str:
        """Generate HTML for a list item."""
        return ''.join(self.generate(child) for child in node.children)
    
    def _generate_color_block(self, node: ColorNode) -> str:
        """Generate HTML for a color-formatted block."""
        content = ''.join(self.generate(child) for child in node.children)
        return create_color_block(node.color, content, node.is_line)
    
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
        content = self.generate(node.children[0])
        return create_wiki_link(content)
    
    def _generate_literal(self, node: Node) -> str:
        """Generate HTML for literal text blocks."""
        content = self.generate(node.children[0])
        return create_literal_text(content)
    
    def _generate_text(self, node: Node) -> str:
        """Generate HTML for plain text content."""
        # Basic HTML escaping
        return node.content.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

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
