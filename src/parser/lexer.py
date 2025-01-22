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
    MLQ_START = auto()  # <<< multi-line quote blocks >>>
    MLQ_END = auto()
    PARENTHESIS_START = auto()
    PARENTHESIS_END = auto()

    # Color tags with context
    COLOR_TAG = auto()    # Anywhere in text, including invalid tags rendered as text

    # Special inline formatting
    EMPHASIS = auto()       # *emphasized text*
    TEMPLATE_PGN = auto()   # {{pgn|...}}
    TEMPLATE_ISBN = auto()  # {{isbn|...}}
    TEMPLATE_WIKIDATA = auto()  # {{wikidata|...}}
    
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

    def handle_emphasis(self) -> Optional[Token]:
        """Process emphasized text (*like this*)."""
        if self.current_char != '*' or self.peek() == ' ':  # Not emphasis if space after *
            return None
            
        # Remember start position
        start_line, start_col = self.line, self.column
        self.advance()  # Skip opening *
        
        # Collect text until closing *
        text = []
        while self.current_char and self.current_char != '*' and self.current_char != '\n':
            text.append(self.current_char)
            self.advance()
            
        if self.current_char == '*' and len(text) <= 40:  # Max length for emphasis
            self.advance()  # Skip closing *
            return Token(TokenType.EMPHASIS, ''.join(text), start_line, start_col)
            
        # Not valid emphasis, reset and return None
        self.pos = start_col
        self.advance()
        return None

    def handle_color_tag(self) -> Optional[Token]:
        """Process color tags without context awareness."""
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
                return Token(TokenType.COLOR_TAG, tag_str, line, col)
                    
        # Invalid tag - reset and return None
        self.pos = start_pos
        self.advance()
        return None

    def handle_template(self) -> Optional[Token]:
        """Process template tags like {{pgn|...}} {{isbn|...}} {{wikidata|...}}."""
        if self.current_char != '{' or self.peek() != '{':
            return None
            
        start_line, start_col = self.line, self.column
        self.advance()  # Skip first {
        self.advance()  # Skip second {
        
        # Read template name
        template = []
        while self.current_char and self.current_char != '|' and self.current_char != '}':
            template.append(self.current_char)
            self.advance()
            
        if self.current_char != '|':
            return None
            
        template_name = ''.join(template)
        content = []
        
        self.advance()  # Skip |
        while self.current_char and not (self.current_char == '}' and self.peek() == '}'):
            content.append(self.current_char)
            self.advance()
            
        if self.current_char == '}' and self.peek() == '}':
            self.advance()  # Skip first }
            self.advance()  # Skip second }
            
            template_type = {
                'pgn': TokenType.TEMPLATE_PGN,
                'isbn': TokenType.TEMPLATE_ISBN,
                'wikidata': TokenType.TEMPLATE_WIKIDATA
            }.get(template_name)
            
            if template_type:
                return Token(template_type, ''.join(content), start_line, start_col)
                
        return None

    def handle_mlq(self) -> Optional[Token]:
        """Process MLQ (multi-line quote) block markers."""
        if self.current_char != '<' and self.current_char != '>':
            return None
            
        line, col = self.line, self.column
        char = self.current_char
        
        if (char == '<' and self.peek() == '<' and self.peek(2) == '<' and 
            (self.at_line_start or self.peek(3) == '\n')):
            self.advance()
            self.advance()
            self.advance()
            return Token(TokenType.MLQ_START, '<<<', line, col)
            
        if char == '>' and self.peek() == '>' and self.peek(2) == '>':
            self.advance()
            self.advance()
            self.advance()
            return Token(TokenType.MLQ_END, '>>>', line, col)
            
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
        """Process URLs."""
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
            line, column = self.line, self.column

            # Skip non-significant whitespace except newlines
            while self.current_char and self.current_char.isspace() and self.current_char != '\n':
                self.advance()

            # Return None if we've hit the end
            if self.current_char is None:
                return None

            # Handle newlines
            if self.current_char == '\n':
                self.advance()
                return Token(TokenType.NEWLINE, '\n', line, column)

            # Check first character to determine which handlers to try
            if self.current_char == '-':
                if token := self.handle_section_break():
                    return token
                    
            elif self.current_char == '<':
                # MLQ blocks, color tags, or literal text
                if self.peek() == '<':
                    if self.peek(2) == '<':
                        if token := self.handle_mlq():
                            return token
                    else:
                        if token := self.handle_literal():
                            return token
                else:
                    if token := self.handle_color_tag():
                        return token
                        
            elif self.current_char == '>':
                if self.peek() == '>':
                    if self.peek(2) == '>':
                        if token := self.handle_mlq():
                            return token
                    else:
                        if token := self.handle_literal():
                            return token
                        
            elif self.at_line_start and self.current_char in '*#>':
                if token := self.handle_list_marker():
                    return token
                    
            elif self.current_char == '{' and self.peek() == '{':
                if token := self.handle_template():
                    return token
                    
            elif self.current_char == '*' and not self.peek().isspace():
                if token := self.handle_emphasis():
                    return token
                    
            elif self.current_char == 'h' and self.peek() == 't':
                if token := self.handle_url():
                    return token
                    
            elif '\u4e00' <= self.current_char <= '\u9fff':
                if token := self.handle_chinese():
                    return token
                    
            elif self.current_char == '(':
                self.in_parentheses += 1
                self.advance()
                return Token(TokenType.PARENTHESIS_START, '(', line, column)
                
            elif self.current_char == ')':
                self.in_parentheses = max(0, self.in_parentheses - 1)
                self.advance()
                return Token(TokenType.PARENTHESIS_END, ')', line, column)
                
            elif self.current_char == '[' and self.peek() == '[':
                self.advance()
                self.advance()
                return Token(TokenType.WIKILINK_START, '[[', line, column)
                
            elif self.current_char == ']' and self.peek() == ']':
                self.advance()
                self.advance()
                return Token(TokenType.WIKILINK_END, ']]', line, column)

            # Collect regular text until we hit a token start
            text = []
            while self.current_char and not (
                self.current_char == '\n' or  # Break on newlines
                self.current_char in '()[]' or  # Break on brackets
                (self.current_char == '<' and self.peek() in {'<', '/'}) or
                (self.current_char == '{' and self.peek() == '{') or
                (self.current_char == '[' and self.peek() == '[') or
                (self.at_line_start and self.current_char in '*#>') or  # List markers at start
                (self.current_char == '*' and not self.peek().isspace()) or
                (self.current_char == 'h' and self.peek() == 't' and self.peek(2) == 't' and self.peek(3) == 'p') or
                ('\u4e00' <= self.current_char <= '\u9fff')
            ):
                text.append(self.current_char)
                self.advance()
                
            if text:
                return Token(TokenType.TEXT, ''.join(text), line, column)

            # Skip any unrecognized characters
            self.advance()

        return None


    def tokenize(self, text: str) -> Generator[Token, None, None]:
        """Convert input text into a stream of tokens."""
        self.init(text)
        while token := self.get_next_token():
            yield token


# Helper function that returns a list instead of a generator
def tokenize(text: str) -> List[Token]:
    """Convenience function to tokenize text and return a list of tokens."""
    lexer = AtacamaLexer()
    return list(lexer.tokenize(text))
