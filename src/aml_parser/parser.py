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
    MORE_TAG = auto()    # More tag (section break)
    HR = auto()          # Horizontal rule (section break)
    MLQ = auto()         # Multi-line quote block
    COLOR_BLOCK = auto() # Color-formatted content
    LIST_ITEM = auto()   # List item with marker
    CHINESE = auto()     # Chinese text requiring annotation
    URL = auto()         # URL link
    WIKILINK = auto()    # Wiki-style link ( [[ foo ]] )
    LITERAL = auto()     # Literal text block ( << foo >> )
    EMPHASIS = auto()    # Emphasized text ( *foo* )
    TITLE = auto()       # In-line title text [# Foo #]
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
        Returns None if the next token does not match the expected type or if there are no more tokens.
        The caller is responsible for handling the None case, often by creating a TEXT node
        for graceful recovery.
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

            if token.type == TokenType.MORE_TAG:
                document.children.append(Node(type=NodeType.MORE_TAG, token=self.consume()))
                continue

            # Handle "<red> <<<" syntax.  Only at start of lines.
            if colored_mlq := self.parse_colored_mlq():
                document.children.append(colored_mlq)
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
                # If parse_inline_content returns None, the token is unhandled at this level.
                # Consume it and add as a TEXT node to the document for robustness.
                unhandled_token_at_doc_level = self.consume()
                if unhandled_token_at_doc_level:
                    document.children.append(Node(type=NodeType.TEXT, token=unhandled_token_at_doc_level))
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

        # Handle title text
        if token.type == TokenType.TITLE_START:
            return self.parse_bracketed_content(
                start_type=TokenType.TITLE_START,
                end_type=TokenType.TITLE_END,
                node_type=NodeType.TITLE)

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

        return None # Token type not recognized for inline content by this dispatcher

    def parse_mlq(self) -> Optional[Node]:
        """Parse a multi-line quote block."""
        start_token = self.expect(TokenType.MLQ_START)
        if not start_token:
            return None
            
        # Create a text node based on start_token for fallback
        text_node_for_fallback = Node(type=NodeType.TEXT, token=Token(
            TokenType.TEXT,
            start_token.value, # This is '<<<'
            start_token.line,
            start_token.column
        ))
        
        parsed_children = []
        while self.peek() and self.peek().type != TokenType.MLQ_END:
            if node := self.parse_inline_content():
                parsed_children.append(node)
            else:
                # If parse_inline_content returns None, consume the unhandled token
                # and add it as a raw text node to preserve content.
                unhandled_token = self.consume()
                if unhandled_token:
                    parsed_children.append(Node(type=NodeType.TEXT, token=unhandled_token))
                
        if self.expect(TokenType.MLQ_END):
            # Successfully parsed MLQ
            mlq_node = Node(type=NodeType.MLQ, token=start_token)
            mlq_node.children = parsed_children
            return mlq_node
        else:
            # No end marker - return as text, appending parsed children to the start_token's text representation
            text_node_for_fallback.children.extend(parsed_children)
            return text_node_for_fallback

    def parse_colored_mlq(self) -> Optional[Node]:
        """Parse a color tag at line start followed by an MLQ block."""
        token = self.peek()
        if not token or token.type != TokenType.COLOR_TAG:
            return None

        saved_position = self.position
        color_token = self.consume()
        color = color_token.value.strip('<>')

        whitespace_tokens = []
        while self.peek() and self.peek().type == TokenType.TEXT and self.peek().value.isspace():
            whitespace_tokens.append(self.consume())

        if not self.peek() or self.peek().type != TokenType.MLQ_START:
            self.position = saved_position
            return None

        mlq = self.parse_mlq()
        if not mlq: # This implies parse_mlq itself might have returned a fallback TEXT node
            self.position = saved_position # Revert if MLQ parsing (even fallback) wasn't what we wanted here
            return None
        
        # If parse_mlq returned a valid MLQ node (not its text fallback)
        if mlq.type == NodeType.MLQ:
            mlq.color = color # Add color attribute to the MLQ node
            return mlq
        else: # parse_mlq returned a text fallback, meaning the MLQ wasn't properly closed.
              # In this context, the colored_mlq construct is invalid. Backtrack.
            self.position = saved_position
            return None


    def parse_list_item(self) -> Optional[ListItemNode]:
        """Parse a list item with its marker."""
        marker_token = self.peek()
        if not marker_token: # Should not happen if called correctly
            return None
            
        marker_types = {
            TokenType.BULLET_LIST_MARKER: 'bullet',
            TokenType.NUMBER_LIST_MARKER: 'number',
            TokenType.ARROW_LIST_MARKER: 'arrow'
        }
        
        # Ensure the token type is a valid list marker before consuming
        if marker_token.type not in marker_types:
            return None # Should not happen based on call site in parse()

        self.consume()  # Consume marker
        children = []
        
        while self.peek() and self.peek().type not in {
            TokenType.NEWLINE, TokenType.SECTION_BREAK,
            TokenType.BULLET_LIST_MARKER, TokenType.NUMBER_LIST_MARKER, TokenType.ARROW_LIST_MARKER
        }:
            if node := self.parse_inline_content():
                children.append(node)
            else:
                unhandled_token = self.consume()
                if unhandled_token:
                    children.append(Node(type=NodeType.TEXT, token=unhandled_token))
        
        if self.peek() and self.peek().type == TokenType.NEWLINE:
            self.consume() # Consume trailing newline for the list item

        return ListItemNode(marker_type=marker_types[marker_token.type], 
                          token=marker_token,
                          children=children)

    def parse_color_block(self) -> Optional[ColorNode]:
        """Parse a color-formatted block."""
        token = self.expect(TokenType.COLOR_TAG)
        if not token:
            return None # Should not happen if called from parse_inline_content correctly
            
        color = token.value.strip('<>')
        children = []
        is_line = not self.current_paren_depth  # Line-level if not in parentheses
        
        # For line-level color blocks, parse until newline or section break
        if is_line:
            while self.peek() and self.peek().type not in {TokenType.NEWLINE, TokenType.SECTION_BREAK}:
                if node := self.parse_inline_content():
                    children.append(node)
                else:
                    unhandled_token = self.consume()
                    if unhandled_token:
                        children.append(Node(type=NodeType.TEXT, token=unhandled_token))
        # If not is_line (i.e., parenthesized like '(<red> content )'),
        # this function only creates the ColorNode. The content *within* the parentheses
        # (after the color tag) is parsed by parse_paren_content's loop.
        
        return ColorNode(color=color, is_line=is_line, token=token, children=children)

    def parse_paren_content(self) -> Optional[Node]:
        """Parse parenthesized content, including nested color tags."""
        start_token = self.expect(TokenType.PARENTHESIS_START)
        if not start_token:
            return None
            
        self.current_paren_depth += 1
        
        color_token_for_paren = None
        # Check if the very next token is a color tag, e.g. '(<red> ...)'
        if self.peek() and self.peek().type == TokenType.COLOR_TAG:
            color_token_for_paren = self.consume()
        
        children_within_paren = []
        while self.peek() and self.peek().type != TokenType.PARENTHESIS_END:
            if node := self.parse_inline_content():
                children_within_paren.append(node)
            else:
                # Unhandled token inside parentheses
                unhandled_token = self.consume()
                if unhandled_token:
                    children_within_paren.append(Node(type=NodeType.TEXT, token=unhandled_token))
        
        end_token = self.expect(TokenType.PARENTHESIS_END)
        self.current_paren_depth -= 1 # Decrement depth regardless of finding end_token or not
        
        if end_token:
            if color_token_for_paren:
                # Case: (<color> child1 child2 )
                color = color_token_for_paren.value.strip('<>')
                return ColorNode(color=color, is_line=False, token=color_token_for_paren, children=children_within_paren)
            else:
                # Case: ( child1 child2 )
                # Represent as: TEXT(token='(') with children: [child1, child2, ..., TEXT(token=')')]
                container = Node(type=NodeType.TEXT, token=start_token) 
                container.children = children_within_paren 
                container.children.append(Node(type=NodeType.TEXT, token=end_token)) 
                return container
        else:
            # No closing parenthesis - fallback to text.
            # The start_token ('(') becomes text. Append collected children.
            # If there was a color_token_for_paren, it's effectively part of the children now if it was consumed.
            # We need to ensure color_token_for_paren is also prepended if it was consumed.
            text_fallback_node = Node(type=NodeType.TEXT, token=Token(
                TokenType.TEXT, start_token.value, start_token.line, start_token.column
            ))
            
            if color_token_for_paren: # If we consumed a color tag but didn't find closing paren
                text_fallback_node.children.append(Node(type=NodeType.TEXT, token=color_token_for_paren))

            text_fallback_node.children.extend(children_within_paren)
            return text_fallback_node

    def parse_wikilink(self) -> Optional[Node]:
        """Parse a wiki-style link. Reuses parse_bracketed_content."""
        return self.parse_bracketed_content(
            start_type=TokenType.WIKILINK_START,
            end_type=TokenType.WIKILINK_END,
            node_type=NodeType.WIKILINK
        )

    def parse_literal(self) -> Optional[Node]:
        """Parse a literal text block. Reuses parse_bracketed_content."""
        return self.parse_bracketed_content(
            start_type=TokenType.LITERAL_START,
            end_type=TokenType.LITERAL_END,
            node_type=NodeType.LITERAL
        )

    def parse_bracketed_content(self, start_type: TokenType, end_type: TokenType, node_type: NodeType) -> Optional[Node]:
        """
        Parse content between matching bracket-style markers.
        Used for wikilinks, literal blocks, and title text.

        :param start_type: Expected start token type
        :param end_type: Expected end token type  
        :param node_type: Type of node to create if successfully parsed
        :return: Parsed node or a TEXT fallback node if brackets are unclosed/malformed.
        """
        start_token = self.expect(start_type)
        if not start_token:
            return None # Should not happen if called correctly

        # Create a text node based on the start_token's original value, for fallback.
        # This node will store the start delimiter as text, and then any parsed children.
        text_fallback_node = Node(type=NodeType.TEXT, token=Token(
            TokenType.TEXT,
            start_token.value, # e.g., "[[" or "<<" or "[#"
            start_token.line,
            start_token.column
        ))

        # Collect content that is between the start and potential end markers.
        # These children will be used for the actual 'node_type' if parsing is successful,
        # OR they will be appended to 'text_fallback_node.children' if parsing fails (e.g. no end marker).
        parsed_children_for_node = []
        
        # Keep track of nesting depth for proper handling of nested brackets
        nesting_depth = 0
        
        while self.peek():
            current_token = self.peek()
            
            # Stop parsing on newline, or if we hit structural elements
            if current_token.type in {TokenType.NEWLINE, TokenType.SECTION_BREAK, TokenType.MORE_TAG}:
                break
                
            # Handle nested start tokens
            if current_token.type == start_type:
                nesting_depth += 1
                
            # Handle end tokens - only break if we're at the top level
            if current_token.type == end_type:
                if nesting_depth == 0:
                    break  # This is our closing token
                else:
                    nesting_depth -= 1
                    
            # Stop if we encounter tokens that typically end color blocks or parentheses
            if current_token.type in {TokenType.PARENTHESIS_END} and nesting_depth == 0:
                break

            if inline_node := self.parse_inline_content():
                parsed_children_for_node.append(inline_node)
            else:
                # Unhandled token within the brackets. Consume and add as raw text.
                unhandled_token = self.consume()
                if unhandled_token:
                    parsed_children_for_node.append(Node(type=NodeType.TEXT, token=unhandled_token))

        if self.expect(end_type): # Successfully found and consumed the end_type token
            # Create the proper node with the original start_token and the collected children.
            return Node(type=node_type, token=start_token, children=parsed_children_for_node)
        else:
            # No end marker found.
            # Return the text_fallback_node, which contains the start delimiter as text,
            # and append the children parsed so far.
            text_fallback_node.children.extend(parsed_children_for_node)
            return text_fallback_node


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
        
    prefix = "  " * indent
    parts = [f"{prefix}{node.type.name}"]
    
    if isinstance(node, ColorNode):
        parts[-1] += f" (color={node.color}, line={node.is_line})"
    elif isinstance(node, ListItemNode):
        parts[-1] += f" (marker={node.marker_type})"
    elif node.token and node.token.value is not None: # Check if value is not None
        # For template nodes, include the template name if available
        if node.type == NodeType.TEMPLATE and node.token.template_name:
            parts[-1] += f" (template_name='{node.token.template_name}')"
        parts[-1] += f": {repr(node.token.value)}"
        
    if node.token:
        parts[-1] += f" @ L{node.token.line}:C{node.token.column}"
        
    for child in node.children:
        child_str = display_ast(child, return_string=True, indent=indent + 1)
        if child_str: # Ensure child_str is not empty or None
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