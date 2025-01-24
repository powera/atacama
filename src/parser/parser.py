"""Parser for the Atacama message formatting system.

This module provides robust parsing of Atacama's message formatting into an Abstract
Syntax Tree (AST). It handles block structures, inline formatting, and special content
types while gracefully recovering from malformed input.
"""

from dataclasses import dataclass
from typing import List, Optional, Iterator, Tuple
from enum import Enum, auto
from .lexer import Token, TokenType

class NodeType(Enum):
    """Types of nodes in the Abstract Syntax Tree."""
    DOCUMENT = auto()    # Root node containing all content
    TEXT = auto()        # Plain text content
    NEWLINE = auto()     # Line break 
    HR = auto()          # Horizontal rule (section break)
    MLQ = auto()         # Multi-line quote block
    COLOR_BLOCK = auto() # Color-formatted content
    LIST_ITEM = auto()   # List item with marker
    CHINESE = auto()     # Chinese text requiring annotation
    URL = auto()         # URL link
    WIKILINK = auto()    # Wiki-style link
    LITERAL = auto()     # Literal text block
    EMPHASIS = auto()    # Emphasized text
    TEMPLATE = auto()    # Template blocks (pgn, isbn, etc)

class Node:
    """Base class for all AST nodes with position tracking."""
    def __init__(self, type: NodeType, token: Optional[Token] = None, children: List['Node'] = None):
        self.type = type
        self.token = token
        self.children = children or []

class ColorNode(Node):
    """Node for color-formatted content."""
    def __init__(self, color: str, is_line: bool, token: Token, children: List[Node] = None):
        super().__init__(NodeType.COLOR_BLOCK, token, children)
        self.color = color
        self.is_line = is_line

class ListItemNode(Node):
    """Node for list items with marker type."""
    def __init__(self, marker_type: str, token: Token, children: List[Node] = None):
        super().__init__(NodeType.LIST_ITEM, token, children)
        self.marker_type = marker_type

class ParseError(Exception):
    """Exception raised for parsing errors. Used internally for control flow."""
    def __init__(self, message: str, token: Optional[Token] = None):
        self.message = message
        self.token = token
        super().__init__(f"{message} at line {token.line}, column {token.column}" if token else message)

class AtacamaParser:
    """Parser for Atacama message formatting that creates an AST."""
    
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

    def expect(self, token_type: TokenType) -> Optional[Token]:
        """
        Consume next token if it matches expected type.
        Returns None and creates text node if no match, allowing for graceful recovery.
        """
        token = self.peek()
        if not token or token.type != token_type:
            return None
        return self.consume()

    def parse(self) -> Node:
        """Parse tokens into an AST."""
        document = Node(type=NodeType.DOCUMENT)
        
        while token := self.peek():
            if token.type == TokenType.SECTION_BREAK:
                document.children.append(Node(type=NodeType.HR, token=self.consume()))
                continue
                
            if token.type == TokenType.MLQ_START:
                if mlq := self.parse_mlq():
                    document.children.append(mlq)
                continue
                
            if token.type in {TokenType.BULLET_LIST_MARKER, 
                            TokenType.NUMBER_LIST_MARKER,
                            TokenType.ARROW_LIST_MARKER}:
                if list_item := self.parse_list_item():
                    document.children.append(list_item)
                continue
                
            # Handle all other content types through unified inline parsing
            if node := self.parse_inline_content():
                document.children.append(node)
            else:
                self.consume()  # Skip invalid token

        return document

    def parse_inline_content(self) -> Optional[Node]:
        """
        Parse all types of inline content including text, formatting, and special elements.
        This is the main parsing function that handles all content types consistently.
        """
        token = self.peek()
        if not token:
            return None

        # Handle basic text content
        if token.type == TokenType.TEXT:
            return Node(type=NodeType.TEXT, token=self.consume())
            
        # Handle newlines
        if token.type == TokenType.NEWLINE:
            return Node(type=NodeType.NEWLINE, token=self.consume())

        # Handle color tags
        if token.type == TokenType.COLOR_TAG:
            return self.parse_color_block()

        # Handle Chinese text
        if token.type == TokenType.CHINESE_TEXT:
            return Node(type=NodeType.CHINESE, token=self.consume())

        # Handle URLs
        if token.type == TokenType.URL:
            return Node(type=NodeType.URL, token=self.consume())

        # Handle wiki links
        if token.type == TokenType.WIKILINK_START:
            return self.parse_wikilink()

        # Handle templates
        if token.type == TokenType.TEMPLATE:
            return Node(type=NodeType.TEMPLATE, token=self.consume())

        # Handle emphasis
        if token.type == TokenType.EMPHASIS:
            return Node(type=NodeType.EMPHASIS, token=self.consume())

        # Handle literal text blocks
        if token.type == TokenType.LITERAL_START:
            return self.parse_literal()

        # Handle parenthesized content
        if token.type == TokenType.PARENTHESIS_START:
            return self.parse_paren_content()

        return None

    def parse_mlq(self) -> Optional[Node]:
        """Parse a multi-line quote block."""
        start_token = self.expect(TokenType.MLQ_START)
        if not start_token:
            return None
            
        mlq = Node(type=NodeType.MLQ, token=start_token)
        
        while self.peek() and self.peek().type != TokenType.MLQ_END:
            if node := self.parse_inline_content():
                mlq.children.append(node)
            else:
                self.consume()
                
        if self.expect(TokenType.MLQ_END):
            return mlq
            
        # No end marker - convert to text
        return Node(type=NodeType.TEXT, token=start_token, 
                   children=[Node(type=NodeType.TEXT, token=Token(
                       TokenType.TEXT, '<<<', start_token.line, start_token.column
                   ))])

    def parse_list_item(self) -> Optional[ListItemNode]:
        """Parse a list item with its marker."""
        marker_token = self.peek()
        if not marker_token:
            return None
            
        marker_types = {
            TokenType.BULLET_LIST_MARKER: 'bullet',
            TokenType.NUMBER_LIST_MARKER: 'number',
            TokenType.ARROW_LIST_MARKER: 'arrow'
        }
        
        self.consume()  # Consume marker
        children = []
        
        while self.peek() and self.peek().type not in {
            TokenType.NEWLINE, TokenType.SECTION_BREAK,
            TokenType.BULLET_LIST_MARKER, TokenType.NUMBER_LIST_MARKER, TokenType.ARROW_LIST_MARKER
        }:
            if node := self.parse_inline_content():
                children.append(node)
            else:
                self.consume()
        
        if self.peek() and self.peek().type == TokenType.NEWLINE:
            self.consume()

        return ListItemNode(marker_type=marker_types[marker_token.type], 
                          token=marker_token,
                          children=children)

    def parse_color_block(self) -> Optional[ColorNode]:
        """Parse a color-formatted block."""
        token = self.expect(TokenType.COLOR_TAG)
        if not token:
            return None
            
        color = token.value.strip('<>')
        children = []
        is_line = not self.current_paren_depth  # Line-level if not in parentheses
        
        # For line-level color blocks, parse until newline or section break
        if is_line:
            while self.peek() and self.peek().type not in {TokenType.NEWLINE, TokenType.SECTION_BREAK}:
                if node := self.parse_inline_content():
                    children.append(node)
                else:
                    self.consume()
        
        return ColorNode(color=color, is_line=is_line, token=token, children=children)

    def parse_paren_content(self) -> Optional[Node]:
        """Parse parenthesized content, including nested color tags."""
        start_token = self.expect(TokenType.PARENTHESIS_START)
        if not start_token:
            return None
            
        self.current_paren_depth += 1
        
        # Check for color tag
        color_token = None
        if self.peek() and self.peek().type == TokenType.COLOR_TAG:
            color_token = self.consume()
        
        children = []
        while self.peek() and self.peek().type != TokenType.PARENTHESIS_END:
            if node := self.parse_inline_content():
                children.append(node)
            else:
                self.consume()
        
        end_token = self.expect(TokenType.PARENTHESIS_END)
        self.current_paren_depth -= 1
        
        if end_token:
            if color_token:
                color = color_token.value.strip('<>')
                return ColorNode(color=color, is_line=False, token=color_token, children=children)
            
            # Plain parenthetical - wrap in text nodes
            container = Node(type=NodeType.TEXT, token=start_token, children=children)
            container.children.append(Node(type=NodeType.TEXT, token=end_token))
            return container
            
        # No closing parenthesis - return as text
        return Node(type=NodeType.TEXT, token=start_token)

    def parse_wikilink(self) -> Optional[Node]:
        """Parse a wiki-style link."""
        start_token = self.expect(TokenType.WIKILINK_START)
        if not start_token:
            return None
            
        node = Node(type=NodeType.WIKILINK, token=start_token)
        
        while self.peek() and self.peek().type != TokenType.WIKILINK_END:
            if inline := self.parse_inline_content():
                node.children.append(inline)
            else:
                self.consume()
        
        if self.expect(TokenType.WIKILINK_END):
            return node
            
        # No end marker - convert to text
        return Node(type=NodeType.TEXT, token=start_token)

    def parse_literal(self) -> Optional[Node]:
        """Parse a literal text block."""
        start_token = self.expect(TokenType.LITERAL_START)
        if not start_token:
            return None
            
        node = Node(type=NodeType.LITERAL, token=start_token)
        
        while self.peek() and self.peek().type != TokenType.LITERAL_END:
            if inline := self.parse_inline_content():
                node.children.append(inline)
            else:
                self.consume()
                
        if self.expect(TokenType.LITERAL_END):
            return node
            
        # No end marker - convert to text
        return Node(type=NodeType.TEXT, token=start_token)


def parse(tokens: Iterator[Token]) -> Node:
    """
    Parse a token stream into an AST.
    Provides main entry point for parsing Atacama content.
    """
    parser = AtacamaParser(tokens)
    return parser.parse()


def display_ast(node: Node, return_string: bool = False, indent: int = 0) -> Optional[str]:
    """
    Display or return a text representation of an AST node and its children.
    
    :param node: Root node of the AST to display
    :param return_string: If True, return the display string instead of printing
    :param indent: Current indentation level (used recursively)
    :return: String representation if return_string=True, None otherwise
    """
    if not node:
        return "" if return_string else None
        
    # Create indentation prefix
    prefix = "  " * indent
    
    # Build node representation
    parts = []
    parts.append(f"{prefix}{node.type.name}")
    
    # Add node-specific details
    if isinstance(node, ColorNode):
        parts[-1] += f" (color={node.color}, line={node.is_line})"
    elif isinstance(node, ListItemNode):
        parts[-1] += f" (marker={node.marker_type})"
    elif node.token and node.token.value:
        parts[-1] += f": {repr(node.token.value)}"
        
    # Add position if available
    if node.token:
        parts[-1] += f" @ L{node.token.line}:C{node.token.column}"
        
    # Process children recursively
    for child in node.children:
        child_str = display_ast(child, return_string=True, indent=indent + 1)
        if child_str:
            parts.append(child_str)
            
    result = "\n".join(parts)
    
    if return_string:
        return result
    else:
        print(result)
        return None

def print_ast(node: Node) -> None:
    """
    Convenience function to print an AST.
    
    :param node: Root node of the AST to display
    """
    display_ast(node, return_string=False)
