from typing import Dict, Optional, List
from .parser import Node, NodeType, TextNode, ColorNode, ListNode

class HTMLGenerator:
    """
    Converts an Atacama AST into formatted HTML following the formal grammar.
    
    This generator creates semantic HTML that preserves the document structure and
    formatting defined by the Atacama markup language. It properly handles the
    priority ordering of formatting elements, with section breaks as the highest
    priority and multi-quote blocks as the second highest.
    """
    
    # Color definitions with their associated emojis and descriptions
    COLORS = {
        'xantham': ('🔥', 'Sarcastic/overconfident'),
        'red': ('💡', 'Forceful/certain'),
        'orange': ('⚔️', 'Counterpoint'),
        'yellow': ('💬', 'Quotes'),
        'quote': ('💬', 'Quotes'),
        'green': ('⚙️', 'Technical'),
        'teal': ('🤖', 'LLM output'),
        'blue': ('✨', 'Voice from beyond'),
        'violet': ('📣', 'Serious'),
        'music': ('🎵', 'Musical'),
        'mogue': ('🌎', 'Actions taken'),
        'gray': ('💭', 'Past stories'),
        'hazel': ('🎭', 'Character voice')
    }

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
        content = '\n'.join(self.generate(child) for child in node.children)
        return (
            f'<blockquote class="multi-quote">\n'
            f'{content}\n'
            f'</blockquote>'
        )
    
    def _generate_paragraph(self, node: Node) -> str:
        """Generate HTML for a paragraph node."""
        content = ''.join(self.generate(child) for child in node.children)
        if not content.strip():
            return ""
        if not content.startswith('<'):  # Don't wrap already-wrapped content
            return f'<p>{content}</p>'
        return content
    
    def _generate_list(self, node: ListNode) -> str:
        """Generate HTML for a list structure."""
        items = []
        for child in node.children:
            item_content = self.generate(child)
            class_name = f"{node.marker_type}-list"
            items.append(f'<li class="{class_name}">{item_content}</li>')
        
        return f'<ul class="atacama-list">\n{"".join(items)}\n</ul>'
    
    def _generate_list_item(self, node: Node) -> str:
        """Generate HTML for a list item."""
        return ''.join(self.generate(child) for child in node.children)
    
    def _generate_color_block(self, node: ColorNode) -> str:
        """Generate HTML for a color-formatted block."""
        content = ''.join(self.generate(child) for child in node.children)
        emoji, desc = self.COLORS.get(node.color, ('❓', 'Unknown'))
        
        # Different structure for line-level vs parenthesized colors
        if node.is_line:
            return (
                f'<div class="color-{node.color} color-line">\n'
                f'<span class="sigil" title="{desc}">{emoji}</span>\n'
                f'<span class="colortext-content">{content}</span>\n'
                f'</div>'
            )
        else:
            return (
                f'<span class="color-{node.color} color-paren">'
                f'<span class="sigil" title="{desc}">{emoji}</span>'
                f'<span class="colortext-content">({content})</span>'
                f'</span>'
            )
    
    def _generate_chinese(self, node: Node) -> str:
        """Generate HTML for Chinese text with annotations."""
        text = node.token.value
        if text in self.annotations:
            ann = self.annotations[text]
            pinyin = ann["pinyin"].replace('"', '&quot;')
            definition = ann["definition"].replace('"', '&quot;')
            return (
                f'<span class="annotated-chinese" '
                f'data-pinyin="{pinyin}" '
                f'data-definition="{definition}">'
                f'{text}</span>'
            )
        return f'<span class="annotated-chinese">{text}</span>'
    
    def _generate_url(self, node: Node) -> str:
        """Generate HTML for a URL with proper attributes."""
        url = node.token.value
        sanitized_url = url.replace('"', '%22')  # Basic URL sanitization
        return (
            f'<a href="{sanitized_url}" '
            f'class="external-link" '
            f'target="_blank" '
            f'rel="noopener noreferrer">{url}</a>'
        )
    
    def _generate_wikilink(self, node: Node) -> str:
        """Generate HTML for a wiki-style link."""
        content = self.generate(node.children[0])
        url = content.replace(' ', '_').replace('"', '%22')
        return (
            f'<a href="https://en.wikipedia.org/wiki/{url}" '
            f'class="wikilink" '
            f'target="_blank">{content}</a>'
        )
    
    def _generate_literal(self, node: Node) -> str:
        """Generate HTML for literal text blocks."""
        content = self.generate(node.children[0])
        return f'<span class="literal-text">{content}</span>'
    
    def _generate_text(self, node: TextNode) -> str:
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
