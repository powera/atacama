from dataclasses import dataclass
from enum import Enum, auto
from typing import List, Generator, Optional, Set
import re

from parser.colorblocks import COLORS

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
    TEMPLATE = auto()       # template, like {{pgn|...}}
    TITLE_START = auto()    # [# Title Format #]
    TITLE_END = auto()
    MORE_TAG = auto()       # --MORE-- tag

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
    template_name: Optional[str] = None  # For template tokens
    
    def __repr__(self) -> str:
        """Readable representation for debugging."""
        template_info = f", template={self.template_name}" if self.template_name else ""
        return f"Token({self.type.name}, '{self.value}', line={self.line}, col={self.column}{template_info})"
    

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
    VALID_COLORS: Set[str] = COLORS.keys()

    def __init__(self):
        """Initialize lexer state."""
        # Input state
        self.text: str = ""
        self.pos: int = 0
        self.line: int = 1
        self.column: int = 0
        self.current_char: Optional[str] = None
        self.last_newline_pos: int = 0

        # Context tracking
        self.in_parentheses: int = 0
        
        # Token buffering
        self.buffered_token: Optional[Token] = None
        self.text_buffer: List[str] = []
        self.buffer_start_line: int = 1
        self.buffer_start_col: int = 0

    def init(self, text: str) -> None:
        """Initialize or reset the lexer with new input."""
        self.text = text
        self.pos = 0
        self.line = 1
        self.column = 0
        self.in_parentheses = 0 
        self.last_newline_pos = 0
        self.buffered_token = None
        self.text_buffer = []
        self.buffer_start_line = 1
        self.buffer_start_col = 0
        self.advance()

    def is_at_line_start(self) -> bool:
        """Check if current position is at the start of a line."""
        # Check characters between last newline and current position
        for i in range(self.last_newline_pos, self.pos - 1):
            if not self.text[i].isspace():
                return False
        return True

    def advance(self) -> None:
        """Advance to the next character and update position tracking."""
        if self.pos < len(self.text):
            self.current_char = self.text[self.pos]
            self.pos += 1
            
            if self.current_char == '\n':
                self.line += 1
                self.column = 0
                self.last_newline_pos = self.pos
            else:
                self.column += 1
        else:
            self.current_char = None

    def advance_n(self, n: int) -> None:
        """Advance the lexer by N characters."""
        for _ in range(n):
            self.advance()

    def peek(self, offset: int = 1) -> Optional[str]:
        """Look ahead in the input stream without advancing."""
        peek_pos = self.pos - 1 + offset
        return self.text[peek_pos] if peek_pos < len(self.text) else None

    def peek_n(self, n: int) -> Optional[str]:
        """Retur the next N characters without advancing."""
        return self.text[self.pos:self.pos + n] if self.pos + n < len(self.text) else None

    def handle_section_break(self) -> Optional[Token]:
        """Process potential section break markers."""
        if self.current_char != '-':
            return None
            
        start_line, start_col = self.line, self.column
        dashes = 0
        
        # Handle --MORE-- tag
        # TODO: Change so we are checking for the whole tag
        if self.peek_n(7) == '-MORE--':
            self.advance_n(8)  # Skip MORE--)
            return Token(TokenType.MORE_TAG, '--MORE--', start_line, start_col)
        
        while self.current_char == '-':
            dashes += 1
            self.advance()
            
        if dashes == 4 and (self.current_char is None or self.current_char.isspace()):
            return Token(TokenType.SECTION_BREAK, '----', start_line, start_col)

        # Not a section break, return as text
        return Token(TokenType.TEXT, '-' * dashes, start_line, start_col)

    def handle_list_marker(self) -> Optional[Token]:
        """Process list markers at the start of lines."""
        if not self.is_at_line_start():
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
        start_pos = self.pos 
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
        self.pos = start_pos
        self.line, self.column = start_line, start_col
        self.current_char = "*"
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
        self.line, self.column = line, col
        self.current_char = "<"
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
            
            return Token(
                type=TokenType.TEMPLATE,
                value=''.join(content),
                line=start_line,
                column=start_col,
                template_name=template_name
            )
                
        return None

    def handle_mlq(self) -> Optional[Token]:
        """Process MLQ (multi-line quote) block markers."""
        if self.current_char != '<' and self.current_char != '>':
            return None
            
        line, col = self.line, self.column
        char = self.current_char
        
        if (char == '<' and self.peek() == '<' and self.peek(2) == '<'):
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

    def buffer_text(self) -> Optional[Token]:
        """Buffer regular text until a token boundary is reached."""
        if not self.current_char:
            return None
            
        line, column = self.line, self.column
        text = []

        while self.current_char and not (
            self.current_char == '\n' or  # Always break on newlines
            self.current_char in '<>*#-[]{}()' or  # Potential token starts/ends
            ('\u4e00' <= self.current_char <= '\u9fff') or  # Chinese characters
            (self.current_char == 'h' and self.peek() == 't' and self.peek(2) == 't' and self.peek(3) == 'p')
        ):
            text.append(self.current_char)
            self.advance()

        if text:
            return Token(TokenType.TEXT, ''.join(text), line, column)
        return None

    def get_next_token(self) -> Optional[Token]:
        """Get the next token from the input stream."""
        # First, return any buffered token from a previous call
        if self.buffered_token:
            token = self.buffered_token
            self.buffered_token = None
            return token

        while self.current_char is not None:
            # If we're starting a new buffer, remember the position
            if not self.text_buffer:
                self.buffer_start_line = self.line
                self.buffer_start_col = self.column

            # First check for newlines since they always break text
            if self.current_char == '\n':
                # If we have buffered text, save the newline and return the text
                if self.text_buffer:
                    self.buffered_token = Token(TokenType.NEWLINE, '\n', self.line, self.column)
                    text = ''.join(self.text_buffer)
                    self.text_buffer = []
                    self.advance()
                    return Token(TokenType.TEXT, text, self.buffer_start_line, self.buffer_start_col)
                # Otherwise just return the newline
                self.advance()
                return Token(TokenType.NEWLINE, '\n', self.line, self.column)

            # Try all specific token handlers
            token = None
            if self.current_char == '-':
                token = self.handle_section_break()
            elif self.current_char == '<':
                if self.peek() == '<':
                    if self.peek(2) == '<':
                        token = self.handle_mlq()
                    else:
                        token = self.handle_literal()
                else:
                    token = self.handle_color_tag()
            elif self.current_char == '>':
                if self.peek() == '>':
                    if self.peek(2) == '>':
                        token = self.handle_mlq()
                    else:
                        token = self.handle_literal()
                elif self.is_at_line_start():
                    token = self.handle_list_marker()
            elif self.current_char in '*#' and self.is_at_line_start():
                token = self.handle_list_marker()
            elif self.current_char == '{' and self.peek() == '{':
                token = self.handle_template()
            elif self.current_char == '*':
                token = self.handle_emphasis()
            elif self.current_char == 'h' and self.peek() == 't':
                token = self.handle_url()
            elif '\u4e00' <= self.current_char <= '\u9fff':
                token = self.handle_chinese()
            elif self.current_char == '[' and self.peek() == '#':
                self.advance()  # consume [
                self.advance()  # consume #
                token = Token(TokenType.TITLE_START, '[#', self.line, self.column)
            elif self.current_char == '#' and self.peek() == ']':
                self.advance()  # consume #
                self.advance()  # consume ]
                token = Token(TokenType.TITLE_END, '#]', self.line, self.column)
            elif self.current_char == '(':
                self.in_parentheses += 1
                self.advance()
                token = Token(TokenType.PARENTHESIS_START, '(', self.line, self.column)
            elif self.current_char == ')':
                self.in_parentheses = max(0, self.in_parentheses - 1)
                self.advance()
                token = Token(TokenType.PARENTHESIS_END, ')', self.line, self.column)
            elif self.current_char == '[' and self.peek() == '[':
                self.advance()
                self.advance()
                token = Token(TokenType.WIKILINK_START, '[[', self.line, self.column)
            elif self.current_char == ']' and self.peek() == ']':
                self.advance()
                self.advance()
                token = Token(TokenType.WIKILINK_END, ']]', self.line, self.column)

            # If we found a token
            if token:
                if self.text_buffer:
                    # Save the token and return the buffered text
                    self.buffered_token = token
                    text = ''.join(self.text_buffer)
                    self.text_buffer = []
                    return Token(TokenType.TEXT, text, self.buffer_start_line, self.buffer_start_col)
                return token

            # If we didn't find a token, add current char to buffer
            self.text_buffer.append(self.current_char)
            self.advance()

        # End of input - return any remaining buffered text
        if self.text_buffer:
            text = ''.join(self.text_buffer)
            self.text_buffer = []
            return Token(TokenType.TEXT, text, self.buffer_start_line, self.buffer_start_col)

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
