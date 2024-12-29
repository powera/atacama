from dataclasses import dataclass
from enum import Enum, auto
from typing import List, Generator, Optional

class TokenType(Enum):
    """Defines all possible token types in the Atacama formatting system."""
    # Structural tokens
    SECTION_BREAK = auto()
    NEWLINE = auto()
    
    # List tokens
    BULLET_LIST_MARKER = auto()
    NUMBER_LIST_MARKER = auto()
    ARROW_LIST_MARKER = auto()

    # Parentheses
    PARENTHESIS_START = auto()
    PARENTHESIS_END = auto()
    
    # Color tokens
    COLOR_BLOCK_TAG = auto()
    
    # Special content tokens
    CHINESE_TEXT = auto()
    URL = auto()
    WIKILINK_START = auto()
    WIKILINK_END = auto()
    LITERAL_START = auto()
    LITERAL_END = auto()
    ASTERISK = auto()

    # Basic content
    TEXT = auto()

@dataclass
class Token:
    """Represents a single token in the input stream."""
    type: TokenType
    value: str
    line: int
    column: int
    
    def __repr__(self):
        """Provide a readable representation for debugging."""
        return f"Token({self.type.name}, '{self.value}', line={self.line}, col={self.column})"

class LexerError(Exception):
    """Custom exception for lexer errors."""
    def __init__(self, message: str, line: int, column: int):
        self.message = message
        self.line = line
        self.column = column
        super().__init__(f"{message} at line {line}, column {column}")

class AtacamaLexer:
    """
    Character-by-character lexical analyzer for Atacama message formatting.
    """
    
    def __init__(self):
        """Initialize the lexer state."""
        self.text = ""
        self.pos = 0
        self.line = 1
        self.column = 1
        self.current_char = None
        
        # Valid color names
        self.colors = {
            'xantham', 'red', 'orange', 'yellow', 'green',
            'teal', 'blue', 'violet', 'mogue', 'gray', 'hazel'
        }

    def init(self, text: str) -> None:
        """Initialize or reset the lexer with new input text."""
        self.text = text
        self.pos = 0
        self.line = 1
        self.column = 1
        self.advance()

    def advance(self) -> None:
        """Move to the next character in the input."""
        if self.pos < len(self.text):
            self.current_char = self.text[self.pos]
            self.pos += 1
            if self.current_char == '\n':
                self.line += 1
                self.column = 1
            else:
                self.column += 1
        else:
            self.current_char = None

    def peek(self, offset: int = 1) -> Optional[str]:
        """Look ahead in the input stream without advancing."""
        peek_pos = self.pos - 1 + offset
        if peek_pos < len(self.text):
            return self.text[peek_pos]
        return None

    def skip_whitespace(self) -> None:
        """Skip whitespace characters except newlines."""
        while self.current_char and self.current_char.isspace() and self.current_char != '\n':
            self.advance()

    def collect_url(self) -> str:
        """Collect characters that form a URL."""
        url = []
        # Handle http:// or https://
        while self.current_char and self.current_char in 'https://':
            url.append(self.current_char)
            self.advance()
        
        # Collect domain and path
        while self.current_char and (self.current_char.isalnum() or 
              self.current_char in '-._/%&?=+#~'):
            url.append(self.current_char)
            self.advance()
            
        return ''.join(url)

    def collect_chinese_text(self) -> str:
        """Collect consecutive Chinese characters."""
        chinese = []
        while self.current_char and '\u4e00' <= self.current_char <= '\u9fff':
            chinese.append(self.current_char)
            self.advance()
        return ''.join(chinese)

    def collect_color_tag(self) -> str:
        """Collect a color tag name."""
        if self.current_char != '<':
            return ''
            
        self.advance()  # Skip '<'
        color = []
        
        while self.current_char and self.current_char != '>':
            color.append(self.current_char)
            self.advance()
            
        if self.current_char == '>':
            self.advance()  # Skip '>'
            color_name = ''.join(color)
            if color_name in self.colors:
                return f'<{color_name}>'
                
        return ''

    def collect_text(self) -> str:
        """Collect regular text characters."""
        text = []
        while self.current_char and not (
            self.current_char.isspace() or
            self.current_char in '(<[*>' or
            '\u4e00' <= self.current_char <= '\u9fff' or
            (self.current_char == 'h' and self.peek() == 't' and 
             self.peek(2) == 't' and self.peek(3) == 'p')
        ):
            text.append(self.current_char)
            self.advance()
        return ''.join(text)

    def get_next_token(self) -> Optional[Token]:
        """
        Get the next token from the input stream.
        Returns None when input is exhausted.
        """
        while self.current_char is not None:
            # Skip non-newline whitespace
            if self.current_char.isspace() and self.current_char != '\n':
                self.skip_whitespace()
                continue

            # Track position for error reporting
            line, column = self.line, self.column

            # Handle section breaks
            if self.current_char == '-':
                count = 1
                self.advance()
                while self.current_char == '-':
                    count += 1
                    self.advance()
                if count == 4:
                    return Token(TokenType.SECTION_BREAK, '----', line, column)
                else:
                    return Token(TokenType.TEXT, '-' * count, line, column)

            # Handle newlines
            if self.current_char == '\n':
                self.advance()
                return Token(TokenType.NEWLINE, '\n', line, column)

            # Handle list markers at start of line
            if self.pos == 1 or self.text[self.pos-2] == '\n':
                if self.current_char == '*' and self.peek().isspace():
                    self.advance()
                    self.skip_whitespace()
                    return Token(TokenType.BULLET_LIST_MARKER, '*', line, column)
                elif self.current_char == '#' and self.peek().isspace():
                    self.advance()
                    self.skip_whitespace()
                    return Token(TokenType.NUMBER_LIST_MARKER, '#', line, column)
                elif self.current_char == '>' and self.peek().isspace():
                    self.advance()
                    self.skip_whitespace()
                    return Token(TokenType.ARROW_LIST_MARKER, '>', line, column)

            # Handle URLs
            if self.current_char == 'h' and self.peek() == 't' and \
               self.peek(2) == 't' and self.peek(3) == 'p':
                url = self.collect_url()
                if url:
                    return Token(TokenType.URL, url, line, column)

            # Handle color tags
            if self.current_char == '<':
                color_tag = self.collect_color_tag()
                if color_tag:
                    return Token(TokenType.COLOR_BLOCK_TAG, color_tag, line, column)

            # Handle wikilinks
            if self.current_char == '[' and self.peek() == '[':
                self.advance()
                self.advance()
                return Token(TokenType.WIKILINK_START, '[[', line, column)
            if self.current_char == ']' and self.peek() == ']':
                self.advance()
                self.advance()
                return Token(TokenType.WIKILINK_END, ']]', line, column)

            # Handle literal text markers
            if self.current_char == '<' and self.peek() == '<':
                self.advance()
                self.advance()
                return Token(TokenType.LITERAL_START, '<<', line, column)
            if self.current_char == '>' and self.peek() == '>':
                self.advance()
                self.advance()
                return Token(TokenType.LITERAL_END, '>>', line, column)

            # Handle parentheses
            if self.current_char == '(':
                self.advance()
                return Token(TokenType.PARENTHESIS_START, '(', line, column)
            if self.current_char == ')':
                self.advance()
                return Token(TokenType.PARENTHESIS_END, ')', line, column)

            # Handle asterisk not at start of line
            if self.current_char == '*':
                self.advance()
                return Token(TokenType.ASTERISK, '*', line, column)

            # Handle Chinese text
            if '\u4e00' <= self.current_char <= '\u9fff':
                chinese = self.collect_chinese_text()
                return Token(TokenType.CHINESE_TEXT, chinese, line, column)

            # Handle regular text
            text = self.collect_text()
            if text:
                return Token(TokenType.TEXT, text, line, column)

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
