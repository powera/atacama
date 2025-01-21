from dataclasses import dataclass
from enum import Enum, auto
from typing import List, Generator, Optional, Set
import re

class TokenType(Enum):
    """Token types for the Atacama formatting system."""
    # Structural tokens
    SECTION_BREAK = auto()
    NEWLINE = auto()
    WHITESPACE = auto()

    # List markers
    BULLET_LIST_MARKER = auto()
    NUMBER_LIST_MARKER = auto()
    ARROW_LIST_MARKER = auto()

    # Block structure
    MULTI_QUOTE_START = auto()
    MULTI_QUOTE_END = auto()
    PARENTHESIS_START = auto()
    PARENTHESIS_END = auto()

    # Color tags with context
    COLOR_LINE_TAG = auto()
    COLOR_PAREN_TAG = auto()

    # Special content
    CHINESE_TEXT = auto()
    URL = auto()
    WIKILINK_START = auto()
    WIKILINK_END = auto()
    LITERAL_START = auto()
    LITERAL_END = auto()

    # Basic content
    TEXT = auto()

@dataclass
class Token:
    """A lexical token with position information."""
    type: TokenType
    value: str
    line: int
    column: int
    
    def __repr__(self) -> str:
        """Readable representation for debugging."""
        return f"Token({self.type.name}, '{self.value}', line={self.line}, col={self.column})"

class LexerError(Exception):
    """Exception raised for lexical analysis errors."""
    def __init__(self, message: str, line: int, column: int):
        self.message = message
        self.line = line
        self.column = column
        super().__init__(f"{message} at line {line}, column {column}")

class AtacamaLexer:
    """
    Lexical analyzer for Atacama message formatting following the formal grammar.
    Handles context-sensitive tokens and maintains state for proper parsing.
    """
    
    # Valid color names in the Atacama system
    VALID_COLORS: Set[str] = {
        'xantham', 'red', 'orange', 'yellow', 'quote', 'green',
        'teal', 'blue', 'violet', 'music', 'mogue', 'gray', 'hazel'
    }

    def __init__(self):
        """Initialize lexer state."""
        # Input state
        self.text: str = ""
        self.pos: int = 0
        self.line: int = 1
        self.column: int = 1
        self.current_char: Optional[str] = None

        # Context tracking
        self.in_parentheses: int = 0
        self.at_line_start: bool = True

    def init(self, text: str) -> None:
        """Initialize or reset the lexer with new input."""
        self.text = text
        self.pos = 0
        self.line = 1
        self.column = 1
        self.in_parentheses = 0
        self.at_line_start = True
        self.advance()

    def advance(self) -> None:
        """Advance to the next character and update position tracking."""
        if self.pos < len(self.text):
            self.current_char = self.text[self.pos]
            self.pos += 1
            
            if self.current_char == '\n':
                self.line += 1
                self.column = 1
                self.at_line_start = True
            else:
                self.column += 1
                if not self.current_char.isspace():
                    self.at_line_start = False
        else:
            self.current_char = None

    def peek(self, offset: int = 1) -> Optional[str]:
        """Look ahead in the input stream without advancing."""
        peek_pos = self.pos - 1 + offset
        return self.text[peek_pos] if peek_pos < len(self.text) else None

    def handle_section_break(self) -> Optional[Token]:
        """Process potential section break markers."""
        if self.current_char != '-':
            return None
            
        start_line, start_col = self.line, self.column
        dashes = 0
        
        while self.current_char == '-':
            dashes += 1
            self.advance()
            
        if dashes == 4 and (self.current_char is None or self.current_char.isspace()):
            return Token(TokenType.SECTION_BREAK, '----', start_line, start_col)
            
        # Not a section break, return as text
        return Token(TokenType.TEXT, '-' * dashes, start_line, start_col)

    def handle_list_marker(self) -> Optional[Token]:
        """Process list markers at the start of lines."""
        if not self.at_line_start:
            return None
            
        line, col = self.line, self.column
        marker = self.current_char
        
        if marker == '*' and self.peek().isspace():
            self.advance()
            return Token(TokenType.BULLET_LIST_MARKER, '*', line, col)
        elif marker == '#' and self.peek().isspace():
            self.advance()
            return Token(TokenType.NUMBER_LIST_MARKER, '#', line, col)
        elif marker == '>' and self.peek().isspace():
            self.advance()
            return Token(TokenType.ARROW_LIST_MARKER, '>', line, col)
            
        return None

    def handle_color_tag(self) -> Optional[Token]:
        """Process color tags with context awareness."""
        if self.current_char != '<':
            return None
            
        start_pos = self.pos
        line, col = self.line, self.column
        
        self.advance()  # Skip '<'
        tag = []
        
        while self.current_char and self.current_char != '>':
            tag.append(self.current_char)
            self.advance()
            
        if self.current_char == '>':
            self.advance()  # Skip '>'
            tag_name = ''.join(tag)
            
            if tag_name in self.VALID_COLORS:
                tag_str = f'<{tag_name}>'
                # Determine tag type based on context
                if self.at_line_start or (self.in_parentheses > 0 and self.text[self.pos-len(tag_str)-1] == '('):
                    return Token(
                        TokenType.COLOR_LINE_TAG if self.at_line_start else TokenType.COLOR_PAREN_TAG,
                        tag_str,
                        line,
                        col
                    )
                    
        # Invalid tag - reset and return None
        self.pos = start_pos
        self.advance()
        return None

    def handle_multi_quote(self) -> Optional[Token]:
        """Process multi-quote block markers."""
        if self.current_char != '<' and self.current_char != '>':
            return None
            
        line, col = self.line, self.column
        char = self.current_char
        
        if (char == '<' and self.peek() == '<' and self.peek(2) == '<' and 
            (self.at_line_start or self.peek(3) == '\n')):
            self.advance()
            self.advance()
            self.advance()
            return Token(TokenType.MULTI_QUOTE_START, '<<<', line, col)
            
        if char == '>' and self.peek() == '>' and self.peek(2) == '>':
            self.advance()
            self.advance()
            self.advance()
            return Token(TokenType.MULTI_QUOTE_END, '>>>', line, col)
            
        return None

    def handle_literal(self) -> Optional[Token]:
        """Process literal text markers."""
        if self.current_char != '<' and self.current_char != '>':
            return None
            
        line, col = self.line, self.column
        
        if self.current_char == '<' and self.peek() == '<':
            self.advance()
            self.advance()
            return Token(TokenType.LITERAL_START, '<<', line, col)
            
        if self.current_char == '>' and self.peek() == '>':
            self.advance()
            self.advance()
            return Token(TokenType.LITERAL_END, '>>', line, col)
            
        return None

    def handle_chinese(self) -> Optional[Token]:
        """Process consecutive Chinese characters."""
        if not self.current_char or not '\u4e00' <= self.current_char <= '\u9fff':
            return None
            
        line, col = self.line, self.column
        chars = []
        
        while self.current_char and '\u4e00' <= self.current_char <= '\u9fff':
            chars.append(self.current_char)
            self.advance()
            
        return Token(TokenType.CHINESE_TEXT, ''.join(chars), line, col)

    def handle_url(self) -> Optional[Token]:
        """Process URLs using regex pattern matching."""
        if self.current_char != 'h':
            return None
            
        line, col = self.line, self.column
        url_pattern = re.compile(r'https?://[a-zA-Z0-9\-.]+(:[0-9]+)?(/[^\s]*)?')
        match = url_pattern.match(self.text[self.pos - 1:])
        
        if match:
            url = match.group(0)
            for _ in range(len(url) - 1):  # -1 because we'll advance once more
                self.advance()
            self.advance()
            return Token(TokenType.URL, url, line, col)
            
        return None

    def get_next_token(self) -> Optional[Token]:
        """Get the next token from the input stream."""
        while self.current_char is not None:
            # Track position for error reporting
            line, column = self.line, self.column

            # Handle whitespace
            if self.current_char.isspace() and self.current_char != '\n':
                whitespace = []
                while self.current_char and self.current_char.isspace() and self.current_char != '\n':
                    whitespace.append(self.current_char)
                    self.advance()
                return Token(TokenType.WHITESPACE, ''.join(whitespace), line, column)

            # Handle newlines
            if self.current_char == '\n':
                self.advance()
                return Token(TokenType.NEWLINE, '\n', line, column)

            # Try all token handlers in priority order
            for handler in [
                self.handle_section_break,
                self.handle_multi_quote,
                self.handle_list_marker,
                self.handle_color_tag,
                self.handle_literal,
                self.handle_url,
                self.handle_chinese
            ]:
                if token := handler():
                    return token

            # Handle parentheses
            if self.current_char == '(':
                self.in_parentheses += 1
                self.advance()
                return Token(TokenType.PARENTHESIS_START, '(', line, column)
                
            if self.current_char == ')':
                self.in_parentheses = max(0, self.in_parentheses - 1)
                self.advance()
                return Token(TokenType.PARENTHESIS_END, ')', line, column)

            # Handle wikilinks
            if self.current_char == '[' and self.peek() == '[':
                self.advance()
                self.advance()
                return Token(TokenType.WIKILINK_START, '[[', line, column)
                
            if self.current_char == ']' and self.peek() == ']':
                self.advance()
                self.advance()
                return Token(TokenType.WIKILINK_END, ']]', line, column)

            # Collect regular text
            if self.current_char:
                text = []
                while self.current_char and not (
                    self.current_char in {'<', '>', '[', ']', '(', ')', '-', '\n', ' ', '\t', '*', '#'}
                    or '\u4e00' <= self.current_char <= '\u9fff'
                    or (self.current_char == 'h' and self.peek() == 't' and self.peek(2) == 't' and self.peek(3) == 'p')
                ):
                    text.append(self.current_char)
                    self.advance()
                if text:
                    return Token(TokenType.TEXT, ''.join(text), line, column)

            # Skip unrecognized characters
            self.advance()

        return None

    def tokenize(self, text: str) -> Generator[Token, None, None]:
        """Convert input text into a stream of tokens."""
        self.init(text)
        while token := self.get_next_token():
            yield token

def tokenize(text: str) -> List[Token]:
    """Convenience function to tokenize text and return a list of tokens."""
    lexer = AtacamaLexer()
    return list(lexer.tokenize(text))
