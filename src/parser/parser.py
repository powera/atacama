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
        """
        Parse tokens into an AST.
        Handles all token types and recovers from malformed input.
        """
        document = Node(type=NodeType.DOCUMENT)
        
        while token := self.peek():
            if token.type == TokenType.TEXT:
                document.children.append(Node(type=NodeType.TEXT, token=self.consume()))

            elif token.type == TokenType.NEWLINE:
                document.children.append(Node(type=NodeType.NEWLINE, token=self.consume()))

            elif token.type == TokenType.SECTION_BREAK:
                document.children.append(Node(type=NodeType.HR, token=self.consume()))

            elif token.type == TokenType.MLQ_START:
                if mlq := self.parse_mlq():
                    document.children.append(mlq)

            elif token.type in {TokenType.BULLET_LIST_MARKER, 
                              TokenType.NUMBER_LIST_MARKER,
                              TokenType.ARROW_LIST_MARKER}:
                if list_item := self.parse_list_item():
                    document.children.append(list_item)

            elif token.type == TokenType.COLOR_TAG:
                if color := self.parse_color_line():
                    document.children.append(color)

            elif token.type == TokenType.CHINESE_TEXT:
                document.children.append(Node(type=NodeType.CHINESE, token=self.consume()))

            elif token.type == TokenType.URL:
                document.children.append(Node(type=NodeType.URL, token=self.consume()))

            elif token.type == TokenType.WIKILINK_START:
                if wikilink := self.parse_wikilink():
                    document.children.append(wikilink)

            elif token.type in {TokenType.TEMPLATE_PGN, TokenType.TEMPLATE_ISBN, TokenType.TEMPLATE_WIKIDATA}:
                document.children.append(Node(type=NodeType.TEMPLATE, token=self.consume()))

            elif token.type == TokenType.PARENTHESIS_START:
                if paren := self.parse_paren_content():
                    document.children.append(paren)

            elif token.type == TokenType.LITERAL_START:
                if literal := self.parse_literal():
                    document.children.append(literal)

            elif token.type == TokenType.EMPHASIS:
                document.children.append(Node(type=NodeType.EMPHASIS, token=self.consume()))

            else:
                # Convert unexpected tokens to text
                document.children.append(Node(type=NodeType.TEXT, token=self.consume()))

        return document

    def parse_mlq(self) -> Optional[Node]:
        """
        Parse a multi-line quote block.
        Returns text node if no valid end marker found.
        """
        start_token = self.expect(TokenType.MLQ_START)
        if not start_token:
            return None
            
        mlq = Node(type=NodeType.MLQ, token=start_token)
        content_tokens = []
        
        while self.peek() and self.peek().type != TokenType.MLQ_END:
            if token := self.peek():
                if token.type == TokenType.NEWLINE:
                    mlq.children.append(Node(type=NodeType.NEWLINE, token=self.consume()))
                elif token.type == TokenType.TEXT:
                    mlq.children.append(Node(type=NodeType.TEXT, token=self.consume()))
                else:
                    if node := self.parse_inline():
                        mlq.children.append(node)
                    else:
                        self.consume()
            content_tokens.append(token)
                
        # Check for proper end marker
        if self.expect(TokenType.MLQ_END):
            return mlq
            
        # No end marker - convert to text
        text_content = '<<<' + ''.join(t.value for t in content_tokens)
        return Node(type=NodeType.TEXT, token=start_token)

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
            if node := self.parse_inline():
                children.append(node)
            else:
                if self.peek() and self.peek().type == TokenType.TEXT:
                    children.append(Node(type=NodeType.TEXT, token=self.consume()))
                else:
                    self.consume()
        
        if self.peek() and self.peek().type == TokenType.NEWLINE:
            self.consume()

        return ListItemNode(marker_type=marker_types[marker_token.type], 
                          token=marker_token,
                          children=children)

    def parse_color_line(self) -> Optional[ColorNode]:
        """Parse a line-level color block."""
        token = self.expect(TokenType.COLOR_TAG)
        if not token:
            return None
            
        color = token.value.strip('<>')
        children = []
        
        while self.peek() and self.peek().type not in {TokenType.NEWLINE, TokenType.SECTION_BREAK}:
            if node := self.parse_inline():
                children.append(node)
            elif self.peek().type == TokenType.TEXT:
                children.append(Node(type=NodeType.TEXT, token=self.consume()))
            else:
                self.consume()
                
        return ColorNode(color=color, is_line=True, token=token, children=children)

    def parse_paren_content(self) -> Optional[Node]:
        """
        Parse parenthesized content, including color tags.
        Maintains proper nesting depth and recovers from errors.
        """
        start_token = self.expect(TokenType.PARENTHESIS_START)
        if not start_token:
            return None
            
        self.current_paren_depth += 1
        content_tokens = [start_token]
        
        # Check for color tag
        color_token = None
        if self.peek() and self.peek().type == TokenType.COLOR_TAG:
            color_token = self.consume()
            content_tokens.append(color_token)
        
        children = []
        while self.peek() and self.peek().type != TokenType.PARENTHESIS_END:
            content_tokens.append(self.peek())
            if node := self.parse_inline():
                children.append(node)
            elif self.peek().type == TokenType.TEXT:
                children.append(Node(type=NodeType.TEXT, token=self.consume()))
            else:
                self.consume()
        
        # Check for proper closing
        end_token = self.expect(TokenType.PARENTHESIS_END)
        if end_token:
            self.current_paren_depth -= 1
            if color_token:
                color = color_token.value.strip('<>')
                return ColorNode(color=color, is_line=False, token=color_token, children=children)
            return Node(type=NodeType.TEXT, token=start_token, children=children)
        
        # No closing parenthesis - convert to text
        text_content = '(' + ''.join(t.value for t in content_tokens)
        return Node(type=NodeType.TEXT, token=start_token)

    def parse_wikilink(self) -> Optional[Node]:
        """Parse a wiki-style link."""
        start_token = self.expect(TokenType.WIKILINK_START)
        if not start_token:
            return None
            
        node = Node(type=NodeType.WIKILINK, token=start_token)
        content_tokens = []
        
        while self.peek() and self.peek().type != TokenType.WIKILINK_END:
            content_tokens.append(self.peek())
            if inline := self.parse_inline():
                node.children.append(inline)
            elif self.peek().type == TokenType.TEXT:
                node.children.append(Node(type=NodeType.TEXT, token=self.consume()))
            else:
                self.consume()
        
        if self.expect(TokenType.WIKILINK_END):
            return node
            
        # No end marker - convert to text
        text_content = '[[' + ''.join(t.value for t in content_tokens)
        return Node(type=NodeType.TEXT, token=start_token)

    def parse_literal(self) -> Optional[Node]:
        """Parse a literal text block."""
        start_token = self.expect(TokenType.LITERAL_START)
        if not start_token:
            return None
            
        node = Node(type=NodeType.LITERAL, token=start_token)
        content_tokens = []
        
        while self.peek() and self.peek().type != TokenType.LITERAL_END:
            content_tokens.append(self.peek())
            if inline := self.parse_inline():
                node.children.append(inline)
            elif self.peek().type == TokenType.TEXT:
                node.children.append(Node(type=NodeType.TEXT, token=self.consume()))
            else:
                self.consume()
                
        if self.expect(TokenType.LITERAL_END):
            return node
            
        # No end marker - convert to text
        text_content = '<<' + ''.join(t.value for t in content_tokens)
        return Node(type=NodeType.TEXT, token=start_token)

    def parse_inline(self) -> Optional[Node]:
        """Parse special inline elements like Chinese text, URLs, etc."""
        token = self.peek()
        if not token:
            return None

        if token.type == TokenType.CHINESE_TEXT:
            return Node(type=NodeType.CHINESE, token=self.consume())
            
        elif token.type == TokenType.URL:
            return Node(type=NodeType.URL, token=self.consume())
            
        elif token.type == TokenType.EMPHASIS:
            return Node(type=NodeType.EMPHASIS, token=self.consume())
            
        elif token.type in {TokenType.TEMPLATE_PGN, TokenType.TEMPLATE_ISBN, TokenType.TEMPLATE_WIKIDATA}:
            return Node(type=NodeType.TEMPLATE, token=self.consume())

        elif token.type == TokenType.PARENTHESIS_START:
            # Delegate to the existing parse_paren_content method for handling parentheses
            return self.parse_paren_content()

        return None

def parse(tokens: Iterator[Token]) -> Node:
    """
    Parse a token stream into an AST.
    Provides main entry point for parsing Atacama content.
    """
    parser = AtacamaParser(tokens)
    return parser.parse()
