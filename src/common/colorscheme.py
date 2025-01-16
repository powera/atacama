import re
from typing import Dict, Pattern, Tuple, Optional, Match
import json

from sqlalchemy.orm.session import Session

from common.logging_config import get_logger
logger = get_logger(__name__)

from common.pinyin import annotate_chinese
from common.models import Email
from common.quotes import save_quotes

class ColorScheme:
    """Color scheme definitions and processing for email content."""
    
    COLORS = {
        'xantham': ('🔥', 'xantham', 'sarcastic, overconfident'),
        'red': ('💡', 'red', 'forceful, certain'),
        'orange': ('⚔️', 'orange', 'counterpoint'),
        'yellow': ('💬', 'yellow', 'quotes'),
        'quote': ('💬', 'quote', 'quotes'),
        'green': ('⚙️', 'green', 'technical explanations'),
        'teal': ('🤖', 'teal', 'LLM output'),
        'blue': ('✨', 'blue', 'voice from beyond'),
        'violet': ('📣', 'violet', 'serious'),
        'music': ('🎵', 'musicnote', 'music note'),
        'mogue': ('🌎', 'mogue', 'actions taken'),
        'gray': ('💭', 'gray', 'past stories'),
        'hazel': ('🎭', 'hazel', 'storytelling'),
    }
    
    def __init__(self):
        """Initialize patterns for processing."""
        # Basic color pattern, only matching specific color names at start of line or in parentheses
        color_names = '|'.join(self.COLORS.keys())
        self.color_pattern = re.compile(
            fr'(?:^[ \t]*&lt;({color_names})&gt;(.+?)(?:\r?\n|$))|'  # Start of line
            fr'\([ \t]*&lt;({color_names})&gt;(.*?)[ \t]*\)',  # In parentheses
            re.DOTALL
        )
        
        # Pattern for inline color tags
        self.inline_color_pattern = re.compile(
            fr'&lt;({color_names})&gt;(.+?)(?:\r?\n|$)',
            re.DOTALL
        )
        
        self.chinese_pattern = re.compile(r'[\u4e00-\u9fff]+')
        self.pgn_pattern = re.compile(r'\{\{pgn\|(.*?)\}\}')
        self.section_break_pattern = re.compile(r'[ \t]*----[ \t]*(?:\r\n|\r|\n|$)')
        self.list_pattern = re.compile(r'^[ \t]*([*#>]|&gt;)[ \t]+(.+?)[ \t]*$', re.MULTILINE)
        self.emphasis_pattern = re.compile(r'\*([^\n*]{1,40})\*')
        self.url_pattern = re.compile(r'https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+[^\s]*')
        self.wikilink_pattern = re.compile(r'\[\[([^]]+)\]\]')

    def sanitize_html(self, text: str) -> str:
        """
        Sanitize HTML while preserving our special color tags for later processing.
        
        :param text: Text to sanitize
        :return: Text with HTML escaped but color tags preserved
        """
        # Escape all HTML
        text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        
        return text

    def wrap_chinese(self, text: str, annotations: Optional[Dict] = None) -> str:
        """
        Wrap Chinese characters in annotated spans.
        
        :param text: Text containing Chinese characters
        :param annotations: Optional dictionary of annotations
        :return: Text with wrapped Chinese characters
        """
        # If no annotations provided, generate them
        if annotations is None:
            annotations = annotate_chinese(text)
            
        def replacer(match: Match) -> str:
            hanzi = match.group(0)
            if annotations and hanzi in annotations:
                ann = annotations[hanzi]
                pinyin = ann["pinyin"].replace('"', '&quot;')
                definition = ann["definition"].replace('&', '&amp;').replace('"', '&quot;')
                return (f'<span class="annotated-chinese" '
                       f'data-pinyin="{pinyin}" '
                       f'data-definition="{definition}">'
                       f'{hanzi}</span>')
            return f'<span class="annotated-chinese">{hanzi}</span>'
            
        return self.chinese_pattern.sub(replacer, text)

    def process_colors(self, text: str, message: Optional[Email] = None,
                       db_session: Optional[Session] = None) -> str:
        """
        Process all color tags.
        
        :param text: Text that may contain color tags
        :param message: the DB object for this message
        :param db_session: the SQLAlchemy/SQLITE connection
        :return: Processed text with color spans and sigils
        """
        def replace_color(match: Match) -> str:
            # Extract matched groups
            para_color, para_text, nested_color, nested_text = match.groups()
            
            # Determine which type matched and get the content
            color = para_color or nested_color
            content = para_text or nested_text
            
            if not color or color not in self.COLORS:
                return match.group(0)
                
            sigil, class_name, _ = self.COLORS[color]
           
            if message and db_session and color in ('yellow', 'quote', 'blue'):
                quote_data = {
                    'text': content.strip(),
                    'quote_type': 'reference'
                }
                save_quotes([quote_data], message, db_session)

            # Handle nested colors (with parentheses)
            if nested_color:
                return (f'<span class="colorblock color-{class_name}">'
                    f'<span class="sigil">{sigil}</span>'
                    f'<span class="colortext-content">({content})</span>'
                    f'</span>')
            # Handle paragraph-level colors
            else:
                return (f'<span class="colorblock color-{class_name}">'
                    f'<span class="sigil">{sigil}</span>'
                    f'<span class="colortext-content">{content}</span>'
                    f'</span>')
                   
        # First process paragraph and nested colors
        processed = self.color_pattern.sub(replace_color, text)
        
        # Then process any remaining inline colors
        def replace_inline(match: Match) -> str:
            color, content = match.groups()
            if color not in self.COLORS:
                return match.group(0)
            sigil, class_name, _ = self.COLORS[color]
            return (f'<span class="colorblock color-{class_name}">'
                   f'<span class="sigil">{sigil}</span>'
                   f'<span class="colortext-content">{content}</span>'
                   f'</span>')
                   
        return self.inline_color_pattern.sub(replace_inline, processed)

    def process_literal_text(self, text: str) -> str:
        """
        Convert <<literal-text>> sections into styled spans.
        
        This processor runs after HTML sanitization, so it looks for
        &lt;&lt;text&gt;&gt; patterns and converts them to
        <span class="literal-text">text</span>.
        
        Args:
            text: Text containing literal text sections marked with double angle brackets
            
        Returns:
            Text with literal sections wrapped in styled spans
        """
        pattern = re.compile(
            r'&lt;&lt;(.*?)&gt;&gt;',
            re.MULTILINE | re.DOTALL
        )
        
        def replacer(match: Match) -> str:
            content = match.group(1).strip()
            return f'<span class="literal-text">{content}</span>'
            
        return pattern.sub(replacer, text)

    def process_pgn(self, text: str) -> str:
        """
        Process FEN chess board notation into visual boards using pure HTML/CSS.
        No external libraries required.
        
        :param text: Text that may contain FEN notation in {{pgn|...}} tags
        :return: Text with FEN notation converted to HTML chess boards
        """
        def fen_to_board(match: Match) -> str:
            fen = match.group(1)
            fen_parts = fen.split()
            position = fen_parts[0]
            to_move = 'white' if len(fen_parts) > 1 and fen_parts[1] == 'w' else 'black'

            board = []
            ranks = position.split('/')  # Get just the piece positions
            
            # Map FEN piece letters to Unicode chess pieces
            pieces = {
                'k': '♔', 'q': '♕', 'r': '♖', 'b': '♗', 'n': '♘', 'p': '♙',  # White pieces
                'K': '♚', 'Q': '♛', 'R': '♜', 'B': '♝', 'N': '♞', 'P': '♟',  # Black pieces
            }
            
            # Process each rank
            for rank_idx, rank in enumerate(ranks):
                cells = []
                file_idx = 0
                for char in rank:
                    if char.isdigit():
                        # Empty squares
                        empty_count = int(char)
                        for _ in range(empty_count):
                            cell_color = 'light' if (rank_idx + file_idx) % 2 == 0 else 'dark'
                            cells.append(f'<div class="chess-cell {cell_color}"></div>')
                            file_idx += 1
                    else:
                        # Square with piece
                        cell_color = 'light' if (rank_idx + file_idx) % 2 == 0 else 'dark'
                        piece = pieces.get(char, '')
                        piece_color = 'white-piece' if char.isupper() else 'black-piece'
                        cells.append(f'<div class="chess-cell {cell_color}"><span class="chess-piece {piece_color}">{piece}</span></div>')
                        file_idx += 1
                board.append(''.join(cells))
            
            # Combine ranks into complete board with row labels and file labels
            files = 'abcdefgh'
            board_html = ['<div class="chess-board">']
           
            # Add turn indicator at top
            board_html.append(f'<div class="chess-turn-indicator {to_move}-to-move">')
            board_html.append(f'<span class="turn-symbol">●</span>')
            board_html.append(f'{to_move.capitalize()} to move')
            board_html.append('</div>')

            # Add file labels at top
            board_html.append('<div class="chess-labels files">')
            board_html.extend(f'<div class="chess-label">{f}</div>' for f in files)
            board_html.append('</div>')
            
            # Add ranks with labels
            for rank_idx, rank in enumerate(board):
                board_html.append(f'<div class="chess-rank">')
                board_html.append(f'<div class="chess-label">{8-rank_idx}</div>')
                board_html.append(rank)
                board_html.append(f'<div class="chess-label">{8-rank_idx}</div>')
                board_html.append('</div>')
            
            # Add file labels at bottom
            board_html.append('<div class="chess-labels files">')
            board_html.extend(f'<div class="chess-label">{f}</div>' for f in files)
            board_html.append('</div>')
            
            board_html.append('</div>')
            return '\n'.join(board_html)
        
        return self.pgn_pattern.sub(fen_to_board, text)

    def process_lists(self, text: str) -> str:
        """
        Convert list markers to HTML lists with appropriate classes.
        
        :param text: Text containing list items
        :return: Processed text with HTML lists
        """
        lines = text.split('\n')
        processed_lines = []
        current_list = []
        list_type = None

        for line in lines:
            match = self.list_pattern.match(line)
            if match:
                marker, content = match.groups()
                current_type = {
                    '*': 'bullet-list',
                    '#': 'number-list',
                    '>': 'arrow-list',
                    '&gt;': 'arrow-list'
                }[marker]
                
                if list_type != current_type:
                    if current_list:
                        processed_lines.append('<ul>')
                        processed_lines.extend(current_list)
                        processed_lines.append('</ul>')
                        current_list = []
                    list_type = current_type
                
                current_list.append(f'<li class="{current_type}">{content}</li>')
            else:
                if current_list:
                    processed_lines.append('<ul>')
                    processed_lines.extend(current_list)
                    processed_lines.append('</ul>')
                    current_list = []
                    list_type = None
                processed_lines.append(line)

        if current_list:
            processed_lines.append('<ul>')
            processed_lines.extend(current_list)
            processed_lines.append('</ul>')

        return '\n'.join(processed_lines)

    def process_emphasis(self, text: str) -> str:
        """Convert *emphasized* text to use <em> tag."""
        def replacer(match: Match) -> str:
            text = match.group(1)
            return f'<em>{content}</em>'
        return self.emphasis_pattern.sub(replacer, text)

    def process_urls(self, text: str) -> str:
        """Convert URLs to clickable links."""
        def replacer(match: Match) -> str:
            url = match.group(0)
            sanitized_url = url.replace('"', '%22')
            return f'<a href="{sanitized_url}" target="_blank" rel="noopener noreferrer">{url}</a>'
        return self.url_pattern.sub(replacer, text)

    def process_wikilinks(self, text: str) -> str:
        """Convert [[wikilinks]] to HTML links."""
        def replacer(match: Match) -> str:
            target = match.group(1)
            url = target.replace(' ', '_').replace('"', '%22')
            return f'<a href="https://en.wikipedia.org/wiki/{url}" class="wikilink" target="_blank">{target}</a>'
        return self.wikilink_pattern.sub(replacer, text)

    def process_content(self, content: str,
                       llm_annotations: Optional[Dict] = None,
                       message: Optional[Email] = None,
                       db_session: Optional[Session] = None) -> str:
        """
        Process text content with all features.
        
        :param content: Raw text content to process
        :param llm_annotations: Optional LLM annotations
        :return: Fully processed HTML content
        """

        if not content:
            return ""

        # The first step is to sanitize HTML, to prevent XSS.
        #
        # This must be the first step.  We do not want to have our own
        # <span> tags touched by this function, which needs to prevent
        # user-submitted <span> tags from rendering.
        content = self.sanitize_html(content)
       
        # Process the *emphasis* tag
        content = self.process_emphasis(content)

        # Process URLs and wikilinks
        content = self.process_urls(content)
        content = self.process_wikilinks(content)
        
        # Process Chinese annotations
        content = self.wrap_chinese(content)
        
        # Process LLM annotations if provided
        if llm_annotations:
            for pos, annotation in llm_annotations.items():
                content = content[:int(pos)] + "🔍✨💡" + content[int(pos):]
        
        # Process lists
        content = self.process_lists(content)
       
        # Process {{pgn}}
        content = self.process_pgn(content)

        # Process all color tags (and store quotes to DB)
        content = self.process_colors(content, message, db_session)
        
        # Process << literal-text >> sections
        content = self.process_literal_text(content)
        
        # Process section breaks
        content = self.section_break_pattern.sub('<hr>', content)
        
        # Wrap remaining content in paragraphs
        paragraphs = []
        for para in content.split('\n'):
            if para.strip():
                if not para.strip().startswith('<'):
                    para = f'<p>{para.strip()}</p>'
                paragraphs.append(para.strip())
        
        return '\n'.join(paragraphs)

    def extract_color_content(self, content: str, color: str) -> list[str]:
        """
        Extract content from specified color tags.
        
        :param content: Text content to process
        :param color: Color tag name to extract
        :return: List of text content found within the specified color tags
        """
        pattern = re.compile(
            fr'<{color}>(.*?)(?:\r?\n|$)',
            re.MULTILINE | re.DOTALL
        )
        matches = pattern.finditer(content)
        return [match.group(1).strip() for match in matches if match.group(1).strip()]
