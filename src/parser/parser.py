from dataclasses import dataclass, field
from typing import List, Optional, Iterator
from enum import Enum, auto
from .lexer import Token, TokenType

class NodeType(Enum):
    """Types of nodes in the Abstract Syntax Tree."""
    DOCUMENT = auto()     # Root node
    SECTION = auto()      # Content between section breaks
    MULTI_QUOTE = auto()  # Multi-paragraph quote block
    PARAGRAPH = auto()    # Regular paragraph
    LIST = auto()         # List container
    LIST_ITEM = auto()    # Single list item
    COLOR_BLOCK = auto()  # Color-formatted content
    CHINESE = auto()      # Chinese text requiring annotation
    URL = auto()         # URL link
    WIKILINK = auto()    # Wiki-style link
    LITERAL = auto()     # Literal text block
    TEXT = auto()        # Plain text content

@dataclass
class Node:
    """Base class for all AST nodes."""
    pass

@dataclass 
class TextNode(Node):
    """Leaf node containing text content."""
    type: NodeType
    content: str
    children: List['Node'] = field(default_factory=list)
    token: Optional[Token] = field(default=None)

@dataclass 
class ColorNode(Node):
    """Node for color-formatted content."""
    type: NodeType
    color: str
    is_line: bool  # True for line-level color, False for parenthesized
    children: List['Node'] = field(default_factory=list)
    token: Optional[Token] = field(default=None)

@dataclass
class ListNode(Node):
    """Node representing a list structure."""
    type: NodeType
    marker_type: str  # 'bullet', 'number', or 'arrow'
    children: List['Node'] = field(default_factory=list)
    token: Optional[Token] = field(default=None)

class ParseError(Exception):
    """Exception raised for parsing errors."""
    def __init__(self, message: str, token: Optional[Token] = None):
        self.message = message
        self.token = token
        location = f" at line {token.line}, column {token.column}" if token else ""
        super().__init__(f"{message}{location}")

class AtacamaParser:
    """Parser for Atacama message formatting following the formal grammar."""
    
    def __init__(self, tokens: Iterator[Token]):
        """Initialize parser with token stream."""
        self.tokens = list(tokens)
        self.position = 0
        self.current_paren_depth = 0
    
    def peek(self, offset: int = 0) -> Optional[Token]:
        """Look ahead in token stream without consuming."""
        pos = self.position + offset
        if pos < len(self.tokens):
            return self.tokens[pos]
        return None
    
    def consume(self) -> Optional[Token]:
        """Consume and return next token."""
        token = self.peek()
        if token:
            self.position += 1
        return token
    
    def expect(self, token_type: TokenType) -> Token:
        """Consume next token, ensuring it matches expected type."""
        token = self.peek()
        if not token or token.type != token_type:
            raise ParseError(
                f"Expected {token_type.name}, got {token.type.name if token else 'END'}", 
                token
            )
        return self.consume()

    def parse(self) -> Node:
        """Parse entire document according to grammar."""
        root = Node(type=NodeType.DOCUMENT)
        
        # Parse sections separated by section breaks
        while self.peek():
            section = self.parse_section()
            if section:
                root.children.append(section)
        
        return root
    
    def parse_section(self) -> Optional[Node]:
        """Parse a section (content between section breaks)."""
        if not self.peek():
            return None
            
        section = Node(type=NodeType.SECTION)
        blocks = []
        
        while self.peek() and self.peek().type != TokenType.SECTION_BREAK:
            # Try to parse a multi-quote block first (second highest priority)
            if self.peek().type == TokenType.MULTI_QUOTE_START:
                blocks.append(self.parse_multi_quote())
            else:
                block = self.parse_block()
                if block:
                    blocks.append(block)
        
        if self.peek() and self.peek().type == TokenType.SECTION_BREAK:
            self.consume()  # Consume section break
            # Consume trailing newlines
            while self.peek() and self.peek().type == TokenType.NEWLINE:
                self.consume()
        
        section.children = blocks
        return section
    
    def parse_multi_quote(self) -> Node:
        """Parse a multi-paragraph quote block."""
        self.expect(TokenType.MULTI_QUOTE_START)
        quote = Node(type=NodeType.MULTI_QUOTE)
        
        while self.peek() and self.peek().type != TokenType.MULTI_QUOTE_END:
            if block := self.parse_block():
                quote.children.append(block)
        
        if self.peek():
            self.expect(TokenType.MULTI_QUOTE_END)
        
        return quote
    
    def parse_block(self) -> Optional[Node]:
        """Parse a block element (paragraph or list)."""
        if not self.peek():
            return None
            
        # Handle list markers
        if self.peek().type in {TokenType.BULLET_LIST_MARKER, 
                               TokenType.NUMBER_LIST_MARKER,
                               TokenType.ARROW_LIST_MARKER}:
            return self.parse_list()
            
        # Handle line-level color tags
        if self.peek().type == TokenType.COLOR_LINE_TAG:
            return self.parse_color_line()
            
        return self.parse_paragraph()
    
    def parse_list(self) -> ListNode:
        """Parse a list and its items."""
        marker_token = self.peek()
        marker_types = {
            TokenType.BULLET_LIST_MARKER: 'bullet',
            TokenType.NUMBER_LIST_MARKER: 'number',
            TokenType.ARROW_LIST_MARKER: 'arrow'
        }
        
        list_node = ListNode(
            type=NodeType.LIST,
            marker_type=marker_types[marker_token.type]
        )
        
        while self.peek() and self.peek().type == marker_token.type:
            self.consume()  # Consume marker
            
            # Parse list item content
            item = Node(type=NodeType.LIST_ITEM)
            content = self.parse_inline_content()
            if content:
                item.children.append(content)
            list_node.children.append(item)
            
            # Handle line endings
            while self.peek() and self.peek().type == TokenType.NEWLINE:
                self.consume()
        
        return list_node
    
    def parse_color_line(self) -> Node:
        """Parse a line-level color block."""
        token = self.expect(TokenType.COLOR_LINE_TAG)
        color = token.value.strip('<>')
        
        content = self.parse_inline_content()
        
        return ColorNode(
            type=NodeType.COLOR_BLOCK,
            children=[content] if content else [],
            color=color,
            is_line=True
        )
    
    def parse_paragraph(self) -> Optional[Node]:
        """Parse a regular paragraph."""
        if not self.peek():
            return None
            
        content = self.parse_inline_content()
        if not content:
            return None
            
        return Node(type=NodeType.PARAGRAPH, children=[content])
    
    def parse_inline_content(self) -> Optional[Node]:
        """Parse inline content including text and inline elements."""
        nodes = []
        current_text = []
        
        def flush_text():
            if current_text:
                nodes.append(TextNode(
                    type=NodeType.TEXT,
                    content=''.join(current_text)
                ))
                current_text.clear()
        
        while token := self.peek():
            if token.type == TokenType.NEWLINE:
                self.consume()
                flush_text()
                break
            
            elif token.type == TokenType.PARENTHESIS_START:
                flush_text()
                nodes.append(self.parse_paren_content())
            
            elif token.type == TokenType.CHINESE_TEXT:
                flush_text()
                nodes.append(Node(
                    type=NodeType.CHINESE,
                    token=self.consume()
                ))
            
            elif token.type == TokenType.URL:
                flush_text()
                nodes.append(Node(
                    type=NodeType.URL,
                    token=self.consume()
                ))
            
            elif token.type == TokenType.WIKILINK_START:
                flush_text()
                nodes.append(self.parse_wikilink())
            
            elif token.type == TokenType.LITERAL_START:
                flush_text()
                nodes.append(self.parse_literal())
            
            elif token.type in {TokenType.TEXT, TokenType.WHITESPACE}:
                current_text.append(self.consume().value)
            
            else:
                break
        
        flush_text()
        
        if not nodes:
            return None
        
        return nodes[0] if len(nodes) == 1 else Node(
            type=NodeType.PARAGRAPH,
            children=nodes
        )
    
    def parse_paren_content(self) -> Node:
        """Parse parenthesized content, including color tags."""
        self.expect(TokenType.PARENTHESIS_START)
        self.current_paren_depth += 1
        
        # Check for color tag
        if self.peek() and self.peek().type == TokenType.COLOR_PAREN_TAG:
            token = self.consume()
            color = token.value.strip('<>')
            content = self.parse_inline_content()
            node = ColorNode(
                type=NodeType.COLOR_BLOCK,
                children=[content] if content else [],
                color=color,
                is_line=False
            )
        else:
            # Regular parenthesized content
            content = self.parse_inline_content()
            node = Node(
                type=NodeType.PARAGRAPH,
                children=[TextNode(
                    type=NodeType.TEXT,
                    content=f"({content.content if isinstance(content, TextNode) else ''})"
                )]
            )
        
        self.expect(TokenType.PARENTHESIS_END)
        self.current_paren_depth -= 1
        return node
    
    def parse_wikilink(self) -> Node:
        """Parse a wiki-style link."""
        self.expect(TokenType.WIKILINK_START)
        text = self.parse_inline_content()
        self.expect(TokenType.WIKILINK_END)
        
        return Node(
            type=NodeType.WIKILINK,
            children=[text] if text else []
        )
    
    def parse_literal(self) -> Node:
        """Parse a literal text block."""
        self.expect(TokenType.LITERAL_START)
        text = self.parse_inline_content()
        self.expect(TokenType.LITERAL_END)
        
        return Node(
            type=NodeType.LITERAL,
            children=[text] if text else []
        )

def parse(tokens: Iterator[Token]) -> Node:
    """Convenience function to parse a token stream into an AST."""
    parser = AtacamaParser(tokens)
    return parser.parse()
