from dataclasses import dataclass
from typing import List, Optional, Iterator
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
    """Base class for all AST nodes."""
    def __init__(self, type: NodeType, children: List['Node'] = None, token: Optional[Token] = None):
        self.type = type
        self.children = children or []
        self.token = token

class TextNode(Node):
    """Leaf node containing text content."""
    def __init__(self, content: str):
        super().__init__(NodeType.TEXT)
        self.content = content

class ColorNode(Node):
    """Node for color-formatted content."""
    def __init__(self, color: str, is_line: bool, children: List['Node'] = None):
        super().__init__(NodeType.COLOR_BLOCK, children)
        self.color = color
        self.is_line = is_line

class ListItemNode(Node):
    """Node for list items with marker type."""
    def __init__(self, marker_type: str, children: List['Node'] = None):
        super().__init__(NodeType.LIST_ITEM, children)
        self.marker_type = marker_type  # 'bullet', 'number', or 'arrow'

class ParseError(Exception):
    """Exception raised for parsing errors."""
    def __init__(self, message: str, token: Optional[Token] = None):
        self.message = message
        self.token = token
        location = f" at line {token.line}, column {token.column}" if token else ""
        super().__init__(f"{message}{location}")

class AtacamaParser:
    """Parser for Atacama message formatting."""
    
    def __init__(self, tokens: Iterator[Token]):
        self.tokens = list(tokens)
        self.position = 0
        self.current_paren_depth = 0
    
    def peek(self, offset: int = 0) -> Optional[Token]:
        pos = self.position + offset
        if pos < len(self.tokens):
            return self.tokens[pos]
        return None
    
    def consume(self) -> Optional[Token]:
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
        """Parse tokens into a flat list of nodes."""
        document = Node(type=NodeType.DOCUMENT)
        
        while token := self.peek():
            if token.type == TokenType.TEXT:
                document.children.append(TextNode(self.consume().value))

            elif token.type == TokenType.NEWLINE:
                document.children.append(Node(type=NodeType.NEWLINE))
                self.consume()

            elif token.type == TokenType.SECTION_BREAK:
                document.children.append(Node(type=NodeType.HR))
                self.consume()

            elif token.type == TokenType.MLQ_START:
                document.children.append(self.parse_mlq())

            elif token.type in {TokenType.BULLET_LIST_MARKER, 
                              TokenType.NUMBER_LIST_MARKER,
                              TokenType.ARROW_LIST_MARKER}:
                document.children.append(self.parse_list_item())

            elif token.type == TokenType.COLOR_TAG:
                document.children.append(self.parse_color_line())

            elif token.type == TokenType.CHINESE_TEXT:
                document.children.append(Node(type=NodeType.CHINESE, token=self.consume()))

            elif token.type == TokenType.URL:
                document.children.append(Node(type=NodeType.URL, token=self.consume()))

            elif token.type == TokenType.WIKILINK_START:
                document.children.append(self.parse_wikilink())

            elif token.type in {TokenType.TEMPLATE_PGN, TokenType.TEMPLATE_ISBN, TokenType.TEMPLATE_WIKIDATA}:
                document.children.append(Node(type=NodeType.TEMPLATE, token=self.consume()))

            elif token.type == TokenType.PARENTHESIS_START:
                document.children.append(self.parse_paren_content())

            elif token.type == TokenType.LITERAL_START:
                document.children.append(self.parse_literal())

            elif token.type == TokenType.EMPHASIS:
                document.children.append(Node(type=NodeType.EMPHASIS, token=self.consume()))

            else:
                self.consume()  # Skip unrecognized tokens

        return document

    def parse_mlq(self) -> Node:
        """Parse a multi-line quote block."""
        self.expect(TokenType.MLQ_START)
        mlq = Node(type=NodeType.MLQ)
        
        while self.peek() and self.peek().type != TokenType.MLQ_END:
            if token := self.peek():
                if token.type == TokenType.NEWLINE:
                    mlq.children.append(Node(type=NodeType.NEWLINE))
                    self.consume()
                elif token.type == TokenType.TEXT:
                    mlq.children.append(TextNode(self.consume().value))
                else:
                    if node := self.parse_inline():
                        mlq.children.append(node)
                    else:
                        self.consume()
        
        if self.peek():
            self.expect(TokenType.MLQ_END)
        
        return mlq

    def parse_list_item(self) -> ListItemNode:
        """Parse a list item with its marker."""
        marker_token = self.peek()
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
                if self.peek().type == TokenType.TEXT:
                    children.append(TextNode(self.consume().value))
                else:
                    self.consume()
        
        return ListItemNode(marker_type=marker_types[marker_token.type], children=children)

    def parse_color_line(self) -> ColorNode:
        """Parse a line-level color block."""
        token = self.expect(TokenType.COLOR_TAG)
        color = token.value.strip('<>')
        children = []
        
        while self.peek() and self.peek().type not in {TokenType.NEWLINE, TokenType.SECTION_BREAK}:
            if node := self.parse_inline():
                children.append(node)
            elif self.peek().type == TokenType.TEXT:
                children.append(TextNode(self.consume().value))
            else:
                self.consume()
                
        return ColorNode(color=color, is_line=True, children=children)

    def parse_paren_content(self) -> Node:
        """Parse parenthesized content, including color tags."""
        self.expect(TokenType.PARENTHESIS_START)
        self.current_paren_depth += 1
        
        # Check for color tag
        if self.peek() and self.peek().type == TokenType.COLOR_TAG:
            token = self.consume()
            color = token.value.strip('<>')
            children = []
            
            while self.peek() and self.peek().type != TokenType.PARENTHESIS_END:
                if node := self.parse_inline():
                    children.append(node)
                elif self.peek().type == TokenType.TEXT:
                    children.append(TextNode(self.consume().value))
                else:
                    self.consume()
                    
            node = ColorNode(color=color, is_line=False, children=children)
        else:
            # Regular parenthesized content
            content = []
            while self.peek() and self.peek().type != TokenType.PARENTHESIS_END:
                if node := self.parse_inline():
                    content.append(node)
                elif self.peek().type == TokenType.TEXT:
                    content.append(TextNode(self.consume().value))
                else:
                    self.consume()
            node = Node(type=NodeType.TEXT, children=content)
        
        self.expect(TokenType.PARENTHESIS_END)
        self.current_paren_depth -= 1
        return node

    def parse_wikilink(self) -> Node:
        """Parse a wiki-style link."""
        self.expect(TokenType.WIKILINK_START)
        children = []
        
        while self.peek() and self.peek().type != TokenType.WIKILINK_END:
            if node := self.parse_inline():
                children.append(node)
            elif self.peek().type == TokenType.TEXT:
                children.append(TextNode(self.consume().value))
            else:
                self.consume()
                
        self.expect(TokenType.WIKILINK_END)
        return Node(type=NodeType.WIKILINK, children=children)

    def parse_literal(self) -> Node:
        """Parse a literal text block."""
        self.expect(TokenType.LITERAL_START)
        children = []
        
        while self.peek() and self.peek().type != TokenType.LITERAL_END:
            if node := self.parse_inline():
                children.append(node)
            elif self.peek().type == TokenType.TEXT:
                children.append(TextNode(self.consume().value))
            else:
                self.consume()
                
        self.expect(TokenType.LITERAL_END)
        return Node(type=NodeType.LITERAL, children=children)

    def parse_inline(self) -> Optional[Node]:
        """Parse special inline elements."""
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

        return None

def parse(tokens: Iterator[Token]) -> Node:
    """Parse a token stream into a flat AST."""
    parser = AtacamaParser(tokens)
    return parser.parse()
