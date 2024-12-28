from typing import Dict, Optional, List
from .parser import Node, NodeType, TextNode, ColorNode, ListNode

class HTMLGenerator:
    """
    Converts an Atacama AST into formatted HTML.
    
    This class walks through an Abstract Syntax Tree produced by the AtacamaParser
    and generates HTML with appropriate styling and structure. It handles all
    Atacama formatting features including:
    - Color formatting with emoji indicators
    - Lists with proper nesting
    - Chinese text with annotation markup
    - URLs and wikilinks with proper attributes
    - Section breaks and paragraphs
    """
    
    # Color definitions with their associated emojis
    COLORS = {
        'xantham': ('🔥', 'Sarcastic/overconfident'),
        'red': ('💡', 'Forceful/certain'),
        'orange': ('⚔️', 'Counterpoint'),
        'yellow': ('💬', 'Quotes'),
        'green': ('⚙️', 'Technical'),
        'teal': ('🤖', 'LLM output'),
        'blue': ('✨', 'Voice from beyond'),
        'violet': ('📣', 'Serious'),
        'mogue': ('🌎', 'Actions taken'),
        'gray': ('💭', 'Past stories'),
        'hazel': ('🎭', 'Character voice')
    }

    def __init__(self, annotations: Optional[Dict] = None):
        """
        Initialize the HTML generator.
        
        :param annotations: Optional dictionary of Chinese text annotations
        """
        self.annotations = annotations or {}
        self.list_stack: List[str] = []  # Track nested list types
    
    def generate(self, node: Node) -> str:
        """
        Generate HTML from an AST node.
        
        This is the main entry point for HTML generation. It dispatches to
        specialized methods based on the node type.
        
        :param node: Root node of the AST
        :return: Generated HTML string
        """
        if not node:
            return ""
            
        # Dispatch to appropriate handler based on node type
        method = getattr(self, f'_generate_{node.type.name.lower()}')
        return method(node)
    
    def _generate_message(self, node: Node) -> str:
        """Generate HTML for the root message node."""
        return '\n'.join(self.generate(child) for child in node.children)
    
    def _generate_paragraph(self, node: Node) -> str:
        """Generate HTML for a paragraph node."""
        content = ''.join(self.generate(child) for child in node.children)
        if not content.startswith('<'):  # Don't wrap already-wrapped content
            return f'<p>{content}</p>'
        return content
    
    def _generate_list(self, node: ListNode) -> str:
        """Generate HTML for a list structure."""
        self.list_stack.append(node.list_type)
        items = []
        for child in node.children:
            item_content = self.generate(child)
            class_name = f"{node.list_type}-list"
            items.append(f'<li class="{class_name}">{item_content}</li>')
        self.list_stack.pop()
        return f'<ul>\n{"".join(items)}\n</ul>'
    
    def _generate_list_item(self, node: Node) -> str:
        """Generate HTML for a list item."""
        return ''.join(self.generate(child) for child in node.children)
    
    def _generate_color_block(self, node: ColorNode) -> str:
        """Generate HTML for a block-level color element."""
        content = ''.join(self.generate(child) for child in node.children)
        emoji, desc = self.COLORS.get(node.color, ('❓', 'Unknown'))
        
        return (
            f'<p class="color-{node.color}">'
            f'<span class="sigil" title="{desc}">{emoji}</span>'
            f'<div class="color-content">{content}</div>'
            f'</p>'
        )
    
    def _generate_color_inline(self, node: ColorNode) -> str:
        """Generate HTML for an inline color element."""
        content = ''.join(self.generate(child) for child in node.children)
        emoji, desc = self.COLORS.get(node.color, ('❓', 'Unknown'))
        
        return (
            f'<span class="color-{node.color}">'
            f'(<span class="sigil" title="{desc}">{emoji}</span>'
            f'<div class="color-content">({content})</div>'
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
        """Generate HTML for a URL."""
        url = node.token.value
        return (f'<a href="{url}" target="_blank" '
                f'rel="noopener noreferrer">{url}</a>')
    
    def _generate_wikilink(self, node: Node) -> str:
        """Generate HTML for a wikilink."""
        # The content is stored in the first child node
        target = self.generate(node.children[0])
        url = target.replace(' ', '_')
        return (f'<a href="https://en.wikipedia.org/wiki/{url}" '
                f'class="wikilink" target="_blank">{target}</a>')
    
    def _generate_literal(self, node: Node) -> str:
        """Generate HTML for literal text."""
        content = self.generate(node.children[0])
        return f'<span class="literal-text">{content}</span>'
    
    def _generate_text(self, node: TextNode) -> str:
        """Generate HTML for plain text content."""
        return node.content
    
    def _generate_break(self, node: Node) -> str:
        """Generate HTML for a section break."""
        return '<hr>'

def generate_html(ast: Node, annotations: Optional[Dict] = None) -> str:
    """
    Convenience function to generate HTML from an AST.
    
    :param ast: Root node of the AST
    :param annotations: Optional dictionary of Chinese text annotations
    :return: Generated HTML string
    """
    generator = HTMLGenerator(annotations)
    return generator.generate(ast)
