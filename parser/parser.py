from dataclasses import dataclass, field
from typing import List, Optional, Union, Iterator
from enum import Enum, auto
from .lexer import Token, TokenType

class NodeType(Enum):
    """Defines the types of nodes in our Abstract Syntax Tree."""
    DOCUMENT = auto()     # Root node type
    FRAME = auto()        # Section between horizontal rules
    PARAGRAPH = auto()    # A paragraph of content
    LIST = auto()         # A list container
    LIST_ITEM = auto()    # Individual list item
    COLOR_BLOCK = auto()  # Color-formatted content
    CHINESE = auto()      # Chinese text with annotations
    URL = auto()         # URL link
    WIKILINK = auto()    # Wiki-style link
    LITERAL = auto()     # Literal text section
    TEXT = auto()        # Plain text content
    BREAK = auto()       # Section break (horizontal rule)
    STAR = auto()        # Asterisk/star character

@dataclass(kw_only=True)
class Node:
    """Base class for all AST nodes."""
    type: NodeType
    children: List['Node'] = field(default_factory=list)
    token: Optional[Token] = None
    
    def __repr__(self):
        return f"{self.type.name}({len(self.children)} children)"

@dataclass(kw_only=True)
class TextNode(Node):
    """Leaf node containing text content."""
    content: str

@dataclass(kw_only=True)
class ColorNode(Node):
    """Node for colored content."""
    color: str

@dataclass(kw_only=True)
class ListNode(Node):
    """Node representing a list structure."""
    list_type: str  # 'bullet', 'number', or 'arrow'
    level: int = 0  # Nesting level

class ParseError(Exception):
    """Custom exception for parsing errors."""
    def __init__(self, message: str, token: Optional[Token] = None):
        self.message = message
        self.token = token
        location = f" at line {token.line}, column {token.column}" if token else ""
        super().__init__(f"{message}{location}")

class AtacamaParser:
    """
    Parser for Atacama message formatting.
    
    This parser implements a recursive descent parser that constructs an Abstract
    Syntax Tree (AST) from the token stream produced by AtacamaLexer. It handles:
    - Document structure (paragraphs, lists)
    - Color formatting (block and inline)
    - Special elements (Chinese text, URLs, wikilinks)
    - Section breaks
    """
    
    def __init__(self, tokens: Iterator[Token]):
        """Initialize the parser with a token stream."""
        self.tokens = list(tokens)  # Convert iterator to list for lookahead
        self.position = 0
        self.list_stack = []  # Track nested list types and levels
        self.paren_level = 0  # Track parenthesis nesting level
    
    def peek(self, offset: int = 0) -> Optional[Token]:
        """Look ahead at a token without consuming it."""
        pos = self.position + offset
        if pos < len(self.tokens):
            return self.tokens[pos]
        return None
    
    def consume(self) -> Optional[Token]:
        """Get and consume the next token."""
        if self.position < len(self.tokens):
            token = self.tokens[self.position]
            self.position += 1
            return token
        return None
    
    def expect(self, token_type: TokenType) -> Token:
        """Expect and consume a token of a specific type."""
        token = self.peek()
        if not token or token.type != token_type:
            raise ParseError(
                f"Expected {token_type.name}, got {token.type.name if token else 'END'}", 
                token
            )
        return self.consume()

    def parse(self) -> Node:
        """Parse the entire document and return the AST."""
        root = Node(type=NodeType.DOCUMENT)
        
        # Parse frames (sections between horizontal rules)
        current_frame = []
        
        while self.peek():
            if self.peek().type == TokenType.SECTION_BREAK:
                if current_frame:
                    root.children.append(self.create_frame_node(current_frame))
                    current_frame = []
                root.children.append(Node(type=NodeType.BREAK))
                self.consume()  # Consume the section break
                # Consume any following newlines
                while self.peek() and self.peek().type == TokenType.NEWLINE:
                    self.consume()
            else:
                if node := self.parse_block():
                    current_frame.append(node)
        
        # Add final frame if it exists
        if current_frame:
            root.children.append(self.create_frame_node(current_frame))
            
        return root
    
    def create_frame_node(self, blocks: List[Node]) -> Node:
        """Create a frame node from a list of block nodes."""
        return Node(type=NodeType.FRAME, children=blocks)
    
    def parse_block(self) -> Optional[Node]:
        """Parse a block element."""
        token = self.peek()
        if not token:
            return None
            
        if token.type in (TokenType.BULLET_LIST_MARKER, 
                         TokenType.NUMBER_LIST_MARKER,
                         TokenType.ARROW_LIST_MARKER):
            return self.parse_list()
            
        return self.parse_paragraph()
    
    def parse_list(self) -> ListNode:
        """Parse a list structure and its items."""
        token = self.peek()
        if not token:
            raise ParseError("Expected list marker", None)
            
        list_types = {
            TokenType.BULLET_LIST_MARKER: 'bullet',
            TokenType.NUMBER_LIST_MARKER: 'number',
            TokenType.ARROW_LIST_MARKER: 'arrow'
        }
        
        list_type = list_types[token.type]
        current_level = len(self.list_stack)
        
        list_node = ListNode(
            type=NodeType.LIST,
            list_type=list_type,
            level=current_level
        )
        self.list_stack.append(list_type)
        
        try:
            while self.peek() and self.peek().type == token.type:
                self.consume()  # Consume the marker
                
                item_node = Node(type=NodeType.LIST_ITEM)
                
                # Check for nested list
                next_token = self.peek()
                if next_token and next_token.type in list_types:
                    item_node.children.append(self.parse_list())
                else:
                    content = self.parse_inline_content()
                    if content:
                        item_node.children.append(content)
                
                list_node.children.append(item_node)
                
                # Handle line endings
                while self.peek() and self.peek().type == TokenType.NEWLINE:
                    self.consume()
                    
        finally:
            self.list_stack.pop()
            
        return list_node
    
    def parse_paragraph(self) -> Node:
        """Parse a paragraph and its content."""
        content = self.parse_inline_content()
        if not content:
            return None
        return Node(type=NodeType.PARAGRAPH, children=[content])
    
    def parse_color_tag(self) -> ColorNode:
        """Parse a color tag, handling nested parentheses properly."""
        self.expect(TokenType.PARENTHESIS_START)
        token = self.expect(TokenType.COLOR_BLOCK_TAG)
        color = token.value.strip('<>')
        
        self.paren_level += 1
        content = self.parse_inline_content()
        self.paren_level -= 1
        
        self.expect(TokenType.PARENTHESIS_END)
        
        return ColorNode(
            type=NodeType.COLOR_BLOCK,
            children=[content] if content else [],
            token=token,
            color=color
        )
    
    def parse_inline_content(self) -> Optional[Node]:
        """Parse inline content including text, colors, and special elements."""
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
                
            elif token.type == TokenType.PARENTHESIS_START and self.peek(1) and \
                 self.peek(1).type == TokenType.COLOR_BLOCK_TAG:
                flush_text()
                nodes.append(self.parse_color_tag())
                
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
                
            elif token.type == TokenType.ASTERISK:
                flush_text()
                self.consume()  # Consume the asterisk
                nodes.append(Node(
                    type=NodeType.STAR,
                    content="⭐"
                ))
                
            elif token.type == TokenType.TEXT:
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
    
    def parse_wikilink(self) -> Node:
        """Parse a wikilink."""
        self.expect(TokenType.WIKILINK_START)
        text_token = self.expect(TokenType.TEXT)
        self.expect(TokenType.WIKILINK_END)
        
        return Node(
            type=NodeType.WIKILINK,
            children=[TextNode(
                type=NodeType.TEXT,
                content=text_token.value,
                token=text_token
            )]
        )
    
    def parse_literal(self) -> Node:
        """Parse literal text."""
        self.expect(TokenType.LITERAL_START)
        text_token = self.expect(TokenType.TEXT)
        self.expect(TokenType.LITERAL_END)
        
        return Node(
            type=NodeType.LITERAL,
            children=[TextNode(
                type=NodeType.TEXT,
                content=text_token.value,
                token=text_token
            )]
        )

def parse(tokens: Iterator[Token]) -> Node:
    """
    Convenience function to parse a token stream and return an AST.
    
    :param tokens: Iterator of Token objects
    :return: Root node of the AST
    :raises ParseError: If the input cannot be parsed
    """
    parser = AtacamaParser(tokens)
    return parser.parse()
