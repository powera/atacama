from dataclasses import dataclass
from enum import Enum, auto
import re
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
    Lexical analyzer for Atacama message formatting.
    
    This lexer processes input text and generates a stream of tokens
    according to Atacama's formatting rules. It handles:
    - Color tags (block and inline)
    - List markers
    - Chinese text
    - URLs and wikilinks
    - Section breaks
    - Literal text sections
    """
    
    def __init__(self):
        """Initialize the lexer with token patterns."""
        # Define valid color names for use in multiple patterns
        color_names = 'xantham|red|orange|yellow|green|teal|blue|violet|mogue|gray|hazel'
        
        # Compile regular expressions for different token types
        # Order matters - more specific patterns should come first
        self.patterns = [
            # Section break pattern - exactly matches 4 hyphens on a line
            (re.compile(r'^\s*-{4}\s*$'), TokenType.SECTION_BREAK),

            # URLs must be checked before other patterns to avoid partial matches
            (re.compile(r'https?://[-\w.]+(?:/[-\w./?%&=]*)?'), TokenType.URL),
            
            # List markers at start of line
            (re.compile(r'^\*\s+'), TokenType.BULLET_LIST_MARKER),
            (re.compile(r'^#\s+'), TokenType.NUMBER_LIST_MARKER),
            (re.compile(r'^(?:>|&gt;)\s+'), TokenType.ARROW_LIST_MARKER),
            
            # Color blocks with specific color names
            (re.compile(f'<({color_names})>'), TokenType.COLOR_BLOCK_TAG),
            
            # Wikilinks
            (re.compile(r'\[\['), TokenType.WIKILINK_START),
            (re.compile(r'\]\]'), TokenType.WIKILINK_END),
            
            # Literal text markers
            (re.compile(r'<<'), TokenType.LITERAL_START),
            (re.compile(r'>>'), TokenType.LITERAL_END),
            
            # Parenthesis markers
            (re.compile(r'('), TokenType.PARENTHESIS_START),
            (re.compile(r')'), TokenType.PARENTHESIS_END),

            # Asterisk (for formatting)
            (re.compile(r'*'), TokenType.ASTERISK),

            # Chinese text (sequence of Chinese characters)
            (re.compile(r'[\u4e00-\u9fff]+'), TokenType.CHINESE_TEXT),
            
            # Newlines (for paragraph detection)
            (re.compile(r'\n'), TokenType.NEWLINE),
        ]
        
        # Pattern for text - excludes special characters and Chinese characters
        self.text_pattern = re.compile(r'[^<>\[\]\n\(\)\u4e00-\u9fff]+')
        
        # Pattern for detecting invalid or unclosed tags
        self.invalid_tag = re.compile(r'<([^>]+)')
        
        # Current position tracking
        self.text = ""
        self.pos = 0
        self.line = 1
        self.column = 1
    
    def tokenize(self, text: str) -> Generator[Token, None, None]:
        """
        Convert input text into a stream of tokens.
        
        Args:
            text: Input text to tokenize
            
        Yields:
            Token objects representing the lexical elements
            
        Raises:
            LexerError: If invalid or malformed input is encountered
        """
        self.text = text
        self.pos = 0
        self.line = 1
        self.column = 1
        
        while self.pos < len(self.text):
            token = self._next_token()
            if token:
                yield token
    
    def _next_token(self) -> Optional[Token]:
        """Find and return the next token in the input stream."""
        current_text = self.text[self.pos:]
        
        # Try each pattern in order
        for pattern, token_type in self.patterns:
            match = pattern.match(current_text)
            if match:
                value = match.group(0)
                token = Token(token_type, value, self.line, self.column)
                
                # Update position and line/column tracking
                self.pos += len(value)
                if token_type == TokenType.NEWLINE:
                    self.line += 1
                    self.column = 1
                else:
                    self.column += len(value)
                
                return token
        
        # If no special pattern matches, try to match text
        match = self.text_pattern.match(current_text)
        if match:
            value = match.group(0)
            token = Token(TokenType.TEXT, value, self.line, self.column)
            self.pos += len(value)
            self.column += len(value)
            return token
        
        # Skip invalid characters
        self.pos += 1
        self.column += 1
        return None

# Helper function for easy tokenization
def tokenize(text: str) -> List[Token]:
    """
    Convenience function to tokenize text and return a list of tokens.
    
    Args:
        text: Input text to tokenize
        
    Returns:
        List of Token objects
    
    Raises:
        LexerError: If invalid or malformed input is encountered
    """
    lexer = AtacamaLexer()
    return list(lexer.tokenize(text))
