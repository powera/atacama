from dataclasses import dataclass, field
from typing import List, Optional, Union, Iterator
from enum import Enum, auto
from .lexer import Token, TokenType

class NodeType(Enum):
    """Defines the types of nodes in our Abstract Syntax Tree."""
    MESSAGE = auto()      # Root node type
    PARAGRAPH = auto()    # A paragraph of content
    LIST = auto()         # A list container
    LIST_ITEM = auto()    # Individual list item
    COLOR_BLOCK = auto()  # Block-level color content
    COLOR_INLINE = auto() # Inline color content
    CHINESE = auto()      # Chinese text with annotations
    URL = auto()         # URL link
    WIKILINK = auto()    # Wiki-style link
    LITERAL = auto()     # Literal text section
    TEXT = auto()        # Plain text content
    BREAK = auto()       # Section break

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
    is_block: bool  # True for block-level, False for inline

@dataclass(kw_only=True)
class ListNode(Node):
    """Node representing a list structure."""
    list_type: str  # 'bullet', 'number', or 'arrow'

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
        """
        Initialize the parser with a token stream.
        
        :param tokens: Iterator yielding Token objects
        """
        self.tokens = list(tokens)  # Convert iterator to list for lookahead
        self.position = 0
    
    def peek(self) -> Optional[Token]:
        """Look at the next token without consuming it."""
        if self.position < len(self.tokens):
            return self.tokens[self.position]
        return None
    
    def consume(self) -> Optional[Token]:
        """Get and consume the next token."""
        if self.position < len(self.tokens):
            token = self.tokens[self.position]
            self.position += 1
            return token
        return None
    
    def expect(self, token_type: TokenType) -> Token:
        """
        Expect and consume a token of a specific type.
        
        :raises ParseError: If the next token isn't of the expected type
        """
        token = self.peek()
        if not token or token.type != token_type:
            raise ParseError(
                f"Expected {token_type.name}, got {token.type.name if token else 'END'}", 
                token
            )
        return self.consume()
    
    def parse(self) -> Node:
        """
        Parse the entire message and return the AST.
        
        :return: Root node of the AST
        :raises ParseError: If the input cannot be parsed
        """
        root = Node(type=NodeType.MESSAGE)
        
        while self.peek():
            if node := self.parse_block():
                root.children.append(node)
        
        return root
    
    def parse_block(self) -> Optional[Node]:
        """Parse a top-level block (paragraph, list, or section break)."""
        token = self.peek()
        if not token:
            return None
            
        if token.type == TokenType.SECTION_BREAK:
            self.consume()
            return Node(type=NodeType.BREAK)
            
        if token.type in (TokenType.BULLET_LIST_MARKER, 
                         TokenType.NUMBER_LIST_MARKER,
                         TokenType.ARROW_LIST_MARKER):
            return self.parse_list()
            
        return self.parse_paragraph()
    
    def parse_list(self) -> Node:
        """Parse a list structure and its items."""
        token = self.peek()
        if not token:
            return None
            
        list_types = {
            TokenType.BULLET_LIST_MARKER: 'bullet',
            TokenType.NUMBER_LIST_MARKER: 'number',
            TokenType.ARROW_LIST_MARKER: 'arrow'
        }
        
        list_type = list_types[token.type]
        list_node = ListNode(type=NodeType.LIST, list_type=list_type)
        
        while self.peek() and self.peek().type == token.type:
            self.consume()  # Consume the marker
            content = self.parse_inline_content()
            if content:
                item = Node(type=NodeType.LIST_ITEM, children=[content])
                list_node.children.append(item)
        
        return list_node
    
    def parse_paragraph(self) -> Node:
        """Parse a paragraph and its inline content."""
        content = self.parse_inline_content()
        if not content:
            return None
        return Node(type=NodeType.PARAGRAPH, children=[content])
    
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
                
            elif token.type == TokenType.COLOR_BLOCK_START:
                flush_text()
                node = self.parse_color_block()
                if node:
                    nodes.append(node)
                    
            elif token.type == TokenType.COLOR_INLINE_START:
                flush_text()
                node = self.parse_color_inline()
                if node:
                    nodes.append(node)
                    
            elif token.type == TokenType.CHINESE_TEXT:
                flush_text()
                nodes.append(self.parse_chinese())
                
            elif token.type == TokenType.URL:
                flush_text()
                nodes.append(self.parse_url())
                
            elif token.type == TokenType.WIKILINK_START:
                flush_text()
                node = self.parse_wikilink()
                if node:
                    nodes.append(node)
                    
            elif token.type == TokenType.LITERAL_START:
                flush_text()
                node = self.parse_literal()
                if node:
                    nodes.append(node)
                    
            elif token.type == TokenType.TEXT:
                current_text.append(self.consume().value)
                
            else:
                break
        
        flush_text()
        
        if not nodes:
            return None
            
        return nodes[0] if len(nodes) == 1 else Node(type=NodeType.PARAGRAPH, children=nodes)

    def parse_color_block(self) -> Node:
        """Parse a block-level color element."""
        start = self.expect(TokenType.COLOR_BLOCK_START)
        color = start.value.strip('<>')
        content = self.parse_inline_content()
        self.expect(TokenType.COLOR_BLOCK_END)
        return ColorNode(
            type=NodeType.COLOR_BLOCK,
            children=[content] if content else [],
            token=start,
            color=color,
            is_block=True
        )
    
    def parse_color_inline(self) -> Node:
        """Parse an inline color element."""
        start = self.expect(TokenType.COLOR_INLINE_START)
        color = start.value.strip('(<>)')
        content = self.parse_inline_content()
        self.expect(TokenType.COLOR_INLINE_END)
        return ColorNode(
            type=NodeType.COLOR_INLINE,
            children=[content] if content else [],
            token=start,
            color=color,
            is_block=False
        )
    
    def parse_chinese(self) -> Node:
        """Parse Chinese text."""
        token = self.expect(TokenType.CHINESE_TEXT)
        return Node(type=NodeType.CHINESE, token=token)
    
    def parse_url(self) -> Node:
        """Parse a URL."""
        token = self.expect(TokenType.URL)
        return Node(type=NodeType.URL, token=token)
    
    def parse_wikilink(self) -> Node:
        """Parse a wikilink."""
        self.expect(TokenType.WIKILINK_START)
        content = self.parse_text()
        self.expect(TokenType.WIKILINK_END)
        return Node(type=NodeType.WIKILINK, children=[content])
    
    def parse_literal(self) -> Node:
        """Parse literal text."""
        self.expect(TokenType.LITERAL_START)
        content = self.parse_text()
        self.expect(TokenType.LITERAL_END)
        return Node(type=NodeType.LITERAL, children=[content])
    
    def parse_text(self) -> Node:
        """Parse plain text."""
        token = self.expect(TokenType.TEXT)
        return TextNode(
            type=NodeType.TEXT,
            content=token.value,
            token=token
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
