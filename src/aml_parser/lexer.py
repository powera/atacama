from dataclasses import dataclass
from enum import Enum, auto
from typing import List, Generator, Optional, Set
import re

from aml_parser.colorblocks import COLORS

class TokenType(Enum):
    """Token types for the Atacama formatting system."""
    # Structural tokens
    SECTION_BREAK = auto()
    NEWLINE = auto()

    # List markers
    BULLET_LIST_MARKER = auto()
    NUMBER_LIST_MARKER = auto()
    ARROW_LIST_MARKER = auto()

    # Block structure
    MLQ_START = auto()  # <<< multi-line quote blocks >>>
    MLQ_END = auto()
    PARENTHESIS_START = auto()
    PARENTHESIS_END = auto()

    # Color tags
    COLOR_TAG = auto()

    # Special inline formatting
    EMPHASIS = auto()       # *emphasized text*
    TEMPLATE = auto()       # template, like {{pgn|...}}
    TITLE_START = auto()    # [# Title Format #]
    TITLE_END = auto()
    MORE_TAG = auto()       # --MORE-- tag

    # Special content
    CHINESE_TEXT = auto()
    URL = auto()
    WIKILINK_START = auto() # [[
    WIKILINK_END = auto()   # ]]
    LITERAL_START = auto()  # <<
    LITERAL_END = auto()    # >>

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
    Lexical analyzer for Atacama message formatting.
    Refactored for cleaner invariants and parsing logic.
    """
    VALID_COLORS: Set[str] = set(COLORS.keys())
    URL_PATTERN = re.compile(r'https?://[a-zA-Z0-9\-._~:/?#\[\]@!$&\'()*+,;=%]+')

    def __init__(self):
        self.init("")

    def init(self, text: str) -> None:
        self.text = text
        self.pos = 0
        self.line = 1
        self.column = 1
        self.in_parentheses_depth = 0
        self.current_char = self.text[self.pos] if self.pos < len(self.text) else None

    def _advance(self) -> None:
        if self.current_char == '\n':
            self.line += 1
            self.column = 1
        else:
            self.column += 1
        
        self.pos += 1
        self.current_char = self.text[self.pos] if self.pos < len(self.text) else None

    def _advance_n(self, n: int) -> None:
        for _ in range(n):
            if self.current_char is None: break
            self._advance()

    def _peek(self, offset: int = 0) -> Optional[str]:
        peek_pos = self.pos + offset
        return self.text[peek_pos] if peek_pos < len(self.text) else None

    def _match_and_consume(self, s: str) -> bool:
        if self.text.startswith(s, self.pos):
            self._advance_n(len(s))
            return True
        return False

    def _try_handle_newline(self, tok_line: int, tok_col: int) -> Optional[Token]:
        if self.current_char == '\n':
            val = self.current_char
            self._advance()
            return Token(TokenType.NEWLINE, val, tok_line, tok_col)
        return None

    def _try_handle_section_break_or_more(self, tok_line: int, tok_col: int) -> Optional[Token]:
        if self.current_char == '-':
            # Check for --MORE-- first (8 characters)
            if self.text.startswith("--MORE--", self.pos):
                self._advance_n(8)
                return Token(TokenType.MORE_TAG, "--MORE--", tok_line, tok_col)
            # Then check for ---- section break (4 characters)
            elif self.text.startswith("----", self.pos):
                peek_after = self._peek(4)
                if peek_after is None or peek_after.isspace() or peek_after == '\n':
                    self._advance_n(4)
                    return Token(TokenType.SECTION_BREAK, "----", tok_line, tok_col)
        return None

    def _try_handle_list_marker(self, tok_line: int, tok_col: int) -> Optional[Token]:
        original_pos, original_ln, original_col = self.pos, self.line, self.column
        
        temp_pos = self.pos
        while temp_pos < len(self.text) and self.text[temp_pos] in ' \t':
            temp_pos +=1
        
        current_marker_char = self.text[temp_pos] if temp_pos < len(self.text) else None
        next_char_after_marker = self.text[temp_pos+1] if temp_pos+1 < len(self.text) else None

        token_type = None
        if current_marker_char == '*' and (next_char_after_marker and next_char_after_marker.isspace()):
            token_type = TokenType.BULLET_LIST_MARKER
        elif current_marker_char == '#' and (next_char_after_marker and next_char_after_marker.isspace()):
            token_type = TokenType.NUMBER_LIST_MARKER
        elif current_marker_char == '>' and (next_char_after_marker and next_char_after_marker.isspace()):
            token_type = TokenType.ARROW_LIST_MARKER

        if token_type:
            self._advance_n(temp_pos - self.pos) 
            marker_val = self.current_char
            marker_actual_line, marker_actual_col = self.line, self.column
            self._advance() 
            return Token(token_type, marker_val, marker_actual_line, marker_actual_col)
        
        return None

    def _try_handle_emphasis(self, tok_line: int, tok_col: int) -> Optional[Token]:
        if self.current_char == '*' and self._peek(1) and self._peek(1) not in ' \n':
            original_pos, original_ln, original_col = self.pos, self.line, self.column
            self._advance()
            
            text_content_start_idx = self.pos
            while self.current_char and self.current_char != '*' and self.current_char != '\n':
                self._advance()
            
            if self.current_char == '*':
                text_val = self.text[text_content_start_idx:self.pos]
                if 0 < len(text_val) <= 40:
                    self._advance()
                    return Token(TokenType.EMPHASIS, text_val, tok_line, tok_col)

            self.pos, self.line, self.column = original_pos, original_ln, original_col
            self.current_char = self.text[self.pos] if self.pos < len(self.text) else None
        return None

    def _try_handle_delimiters(self, tok_line: int, tok_col: int,
                               open_delim: str, close_delim: str,
                               start_type: TokenType, end_type: TokenType) -> Optional[Token]:
        if self._match_and_consume(open_delim):
            return Token(start_type, open_delim, tok_line, tok_col)
        if self._match_and_consume(close_delim):
            return Token(end_type, close_delim, tok_line, tok_col)
        return None

    def _try_handle_color_tag(self, tok_line: int, tok_col: int) -> Optional[Token]:
        if self.current_char == '<':
            original_pos, original_ln, original_col = self.pos, self.line, self.column
            self._advance() 
            
            tag_name_chars = []
            while self.current_char and self.current_char.isalnum():
                tag_name_chars.append(self.current_char)
                self._advance()
            
            tag_name = "".join(tag_name_chars)
            if self.current_char == '>' and tag_name in self.VALID_COLORS:
                self._advance() 
                return Token(TokenType.COLOR_TAG, f"<{tag_name}>", tok_line, tok_col)

            self.pos, self.line, self.column = original_pos, original_ln, original_col
            self.current_char = self.text[self.pos] if self.pos < len(self.text) else None
        return None

    def _try_handle_template(self, tok_line: int, tok_col: int) -> Optional[Token]:
        if self.text.startswith("{{", self.pos):
            original_pos, original_ln, original_col = self.pos, self.line, self.column
            self._advance_n(2)

            name_chars = []
            while self.current_char and self.current_char != '|' and not self.text.startswith("}}", self.pos):
                name_chars.append(self.current_char)
                self._advance()
            
            if self.current_char == '|':
                template_name = "".join(name_chars)
                self._advance() 
                
                value_chars = []
                nesting_level = 0
                while self.current_char:
                    if self.text.startswith("{{", self.pos):
                        nesting_level +=1
                        value_chars.append("{{")
                        self._advance_n(2)
                        continue
                    if self.text.startswith("}}", self.pos):
                        if nesting_level == 0:
                            break
                        nesting_level -=1
                        value_chars.append("}}")
                        self._advance_n(2)
                        continue
                    value_chars.append(self.current_char)
                    self._advance()
                
                if self.text.startswith("}}", self.pos):
                    self._advance_n(2) 
                    return Token(TokenType.TEMPLATE, "".join(value_chars), tok_line, tok_col, template_name=template_name)

            self.pos, self.line, self.column = original_pos, original_ln, original_col
            self.current_char = self.text[self.pos] if self.pos < len(self.text) else None
        return None

    def _try_handle_chinese(self, tok_line: int, tok_col: int) -> Optional[Token]:
        if self.current_char and '\u4e00' <= self.current_char <= '\u9fff':
            start_idx = self.pos
            while self.current_char and '\u4e00' <= self.current_char <= '\u9fff':
                self._advance()
            value = self.text[start_idx:self.pos]
            return Token(TokenType.CHINESE_TEXT, value, tok_line, tok_col)
        return None

    def _try_handle_url(self, tok_line: int, tok_col: int) -> Optional[Token]:
        if self.text.startswith("http", self.pos):
            match = self.URL_PATTERN.match(self.text, self.pos)
            if match:
                url = match.group(0)
                self._advance_n(len(url))
                return Token(TokenType.URL, url, tok_line, tok_col)
        return None

    def _handle_text(self, tok_line: int, tok_col: int) -> Token:
        start_idx = self.pos
        
        while self.current_char is not None:
            if self.current_char == '\n': break 

            if self.text.startswith("--MORE--", self.pos): break
            peek4 = self._peek(4)
            if self.text.startswith("----", self.pos) and (peek4 is None or peek4.isspace() or peek4 == '\n'): break
            
            if self.text.startswith("<<<", self.pos): break
            if self.text.startswith(">>>", self.pos): break
            if self.text.startswith("<<", self.pos): break
            if self.text.startswith(">>", self.pos): break
            
            if self.current_char == '<':
                temp_tag_name_start = self.pos + 1
                temp_tag_name_end = temp_tag_name_start
                while temp_tag_name_end < len(self.text) and self.text[temp_tag_name_end].isalnum():
                    temp_tag_name_end += 1
                if temp_tag_name_end < len(self.text) and self.text[temp_tag_name_end] == '>':
                    if self.text[temp_tag_name_start:temp_tag_name_end] in self.VALID_COLORS:
                        break

            if self.text.startswith("{{", self.pos): break
            
            if self.current_char == '*' and self._peek(1) and self._peek(1) not in ' \n':
                break 
            
            if self.text.startswith("http", self.pos):
                if self.URL_PATTERN.match(self.text, self.pos):
                    break

            if '\u4e00' <= self.current_char <= '\u9fff': break

            if self.text.startswith("[#", self.pos): break 
            if self.text.startswith("#]", self.pos): break 
            if self.text.startswith("[[", self.pos): break 
            if self.text.startswith("]]", self.pos): break 

            if self.current_char == '(': break 
            if self.current_char == ')': break 

            if self.column == 1:
                temp_marker_pos = self.pos
                while temp_marker_pos < len(self.text) and self.text[temp_marker_pos] in ' \t':
                    temp_marker_pos += 1
                
                if temp_marker_pos < len(self.text):
                    marker_char_candidate = self.text[temp_marker_pos]
                    next_after_marker_candidate = self.text[temp_marker_pos+1] if temp_marker_pos+1 < len(self.text) else None
                    if marker_char_candidate in "*#>" and \
                       (next_after_marker_candidate and next_after_marker_candidate.isspace()):
                        break
            
            self._advance()

        if self.pos == start_idx and self.current_char is not None:
            self._advance()
            
        value = self.text[start_idx:self.pos]
        return Token(TokenType.TEXT, value, tok_line, tok_col)

    def get_next_token(self) -> Optional[Token]:
        if self.current_char is None:
            return None

        tok_line, tok_col = self.line, self.column

        token = self._try_handle_newline(tok_line, tok_col)
        if token: return token
        
        # No _try_handle_whitespace here. TEXT will consume it.
        
        token = self._try_handle_section_break_or_more(tok_line, tok_col)
        if token: return token
        
        token = self._try_handle_delimiters(tok_line, tok_col, "<<<", ">>>", TokenType.MLQ_START, TokenType.MLQ_END)
        if token: return token
        token = self._try_handle_delimiters(tok_line, tok_col, "<<", ">>", TokenType.LITERAL_START, TokenType.LITERAL_END)
        if token: return token
        
        token = self._try_handle_color_tag(tok_line, tok_col)
        if token: return token

        token = self._try_handle_template(tok_line, tok_col)
        if token: return token

        if tok_col == 1:
            list_marker_token = self._try_handle_list_marker(tok_line, tok_col)
            if list_marker_token: return list_marker_token
        
        token = self._try_handle_emphasis(tok_line, tok_col)
        if token: return token

        token = self._try_handle_url(tok_line, tok_col)
        if token: return token
        
        token = self._try_handle_chinese(tok_line, tok_col)
        if token: return token

        token = self._try_handle_delimiters(tok_line, tok_col, "[#", "#]", TokenType.TITLE_START, TokenType.TITLE_END)
        if token: return token
        token = self._try_handle_delimiters(tok_line, tok_col, "[[", "]]", TokenType.WIKILINK_START, TokenType.WIKILINK_END)
        if token: return token

        if self.current_char == '(':
            self._advance()
            self.in_parentheses_depth += 1
            return Token(TokenType.PARENTHESIS_START, '(', tok_line, tok_col)
        if self.current_char == ')':
            self._advance()
            self.in_parentheses_depth -= 1
            return Token(TokenType.PARENTHESIS_END, ')', tok_line, tok_col)

        return self._handle_text(tok_line, tok_col)

    def tokenize(self, text: str) -> Generator[Token, None, None]:
        self.init(text)
        while self.current_char is not None:
            token = self.get_next_token()
            if token: # Ensure token is not empty
                if token.value: # Only yield tokens that have content
                    yield token
            else:
                raise LexerError("Lexer failed to produce a token or advance.", self.line, self.column)
        
def tokenize(text: str) -> List[Token]:
    lexer = AtacamaLexer()
    return list(lexer.tokenize(text))