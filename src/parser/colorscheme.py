"""Regex-based content processing using HTML generation functions."""

import re
from typing import Dict, Optional, Match
from sqlalchemy.orm.session import Session

from common.logging_config import get_logger
logger = get_logger(__name__)

from common.pinyin import annotate_chinese
from common.models import Email
from common.quotes import save_quotes
import common.chess

from parser.colorblocks import *  # Import HTML generation functions

class ColorScheme:
    """Color scheme definitions and content processing using regex patterns."""
    
    def __init__(self):
        """Initialize patterns for processing."""
        color_names = '|'.join(COLORS.keys())
        
        # Match color tags at line start or in parentheses
        self.color_pattern = re.compile(
            fr'(?:^[ \t]*&lt;({color_names})&gt;(.+?)(?:\r?\n|$))|'  # Line start
            fr'\([ \t]*&lt;({color_names})&gt;(.*?)[ \t]*\)',        # In parentheses
            re.MULTILINE
        )
        
        # Match remaining inline color tags
        self.inline_color_pattern = re.compile(
            fr'&lt;({color_names})&gt;(.+?)(?:\r?\n|$)'
        )
        
        self.chinese_pattern = re.compile(r'[\u4e00-\u9fff]+')
        self.pgn_pattern = re.compile(r'\{\{pgn\|(.*?)\}\}')
        self.section_break_pattern = re.compile(r'[ \t]*----[ \t]*(?:\r\n|\r|\n|$)')
        self.multiline_block_pattern = re.compile(
            r'&lt;&lt;&lt;[ \t]*([^\n].*?)(?:&gt;&gt;&gt;|(\n[ \t]*----[ \t]*(?:\r?\n|$)))',
            re.DOTALL
        )
        self.paragraph_break_pattern = re.compile(r'\n\s*\n')
        self.list_pattern = re.compile(
            r'^[ \t]*([*#]|&gt;)[ \t]+(.+?)[ \t]*$',
            re.MULTILINE
        )
        self.emphasis_pattern = re.compile(r'\*([^\n*]{1,40})\*')
        self.url_pattern = re.compile(r'https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+[^\s]*')
        self.wikilink_pattern = re.compile(r'\[\[([^]]+)\]\]')
        self.literal_pattern = re.compile(r'&lt;&lt;(.*?)&gt;&gt;')

    def sanitize_html(self, text: str) -> str:
        """Basic HTML escaping while preserving our special tags."""
        return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

    def wrap_chinese(self, text: str, annotations: Optional[Dict] = None) -> str:
        """Process Chinese text with annotations."""
        if annotations is None:
            annotations = annotate_chinese(text)
            
        def replacer(match: Match) -> str:
            hanzi = match.group(0)
            if annotations and hanzi in annotations:
                ann = annotations[hanzi]
                return create_chinese_annotation(
                    hanzi=hanzi,
                    pinyin=ann["pinyin"],
                    definition=ann["definition"]
                )
            return create_chinese_annotation(hanzi=hanzi)
            
        return self.chinese_pattern.sub(replacer, text)

    def process_colors(self, text: str, message: Optional[Email] = None,
                      db_session: Optional[Session] = None) -> str:
        """Process color tags and save quotes if needed."""
        def replace_color(match: Match) -> str:
            para_color, para_text, nested_color, nested_text = match.groups()
            color = para_color or nested_color
            content = para_text or nested_text
            
            if not color or color not in COLORS:
                return match.group(0)
                
            if message and db_session and color in ('yellow', 'quote', 'blue'):
                save_quotes([{'text': content.strip(), 'quote_type': 'reference'}],
                          message, db_session)
                
            return create_color_block(
                color=color,
                content=content,
                is_line=bool(para_color)  # True for line-level, False for nested
            )
                   
        # Process paragraph and nested colors first
        processed = self.color_pattern.sub(replace_color, text)
        
        # Process any remaining inline colors
        def replace_inline(match: Match) -> str:
            color, content = match.groups()
            if color not in COLORS:
                return match.group(0)
            return create_color_block(color=color, content=content)
                   
        return self.inline_color_pattern.sub(replace_inline, processed)

    def process_multiline_blocks(self, text: str) -> str:
        """Process multi-line text blocks."""
        def replacer(match: Match) -> str:
            content = match.group(1)
            section_break = match.group(2)
            
            # Split into paragraphs and clean up
            paragraphs = [p.strip().replace('\n', ' ') 
                         for p in self.paragraph_break_pattern.split(content) 
                         if p.strip()]
            
            result = create_multiline_block(paragraphs)
            if section_break:
                result += "\n----"
            return result
            
        return self.multiline_block_pattern.sub(replacer, text)

    def process_lists(self, text: str) -> str:
        """Process list markers and items."""
        lines = text.split('\n')
        processed_lines = []
        current_list = []
        list_type = None

        for line in lines:
            match = self.list_pattern.match(line)
            if match:
                marker, content = match.groups()
                current_type = {
                    '*': 'bullet',
                    '#': 'number',
                    '>': 'arrow',
                    '&gt;': 'arrow'
                }[marker]
                
                if list_type != current_type:
                    if current_list:
                        processed_lines.append(create_list_container(current_list))
                        current_list = []
                    list_type = current_type
                
                current_list.append(create_list_item(content, current_type))
            else:
                if current_list:
                    processed_lines.append(create_list_container(current_list))
                    current_list = []
                    list_type = None
                processed_lines.append(line)

        if current_list:
            processed_lines.append(create_list_container(current_list))

        return '\n'.join(processed_lines)

    def process_content(self, content: str, llm_annotations: Optional[Dict] = None,
                       message: Optional[Email] = None,
                       db_session: Optional[Session] = None) -> str:
        """Process all content features in the correct order."""
        if not content:
            return ""

        # First sanitize HTML to prevent XSS
        content = self.sanitize_html(content)
       
        # Process inline formatting
        content = self.emphasis_pattern.sub(lambda m: create_emphasis(m.group(1)), content)
        content = self.url_pattern.sub(lambda m: create_url_link(m.group(0)), content)
        content = self.wikilink_pattern.sub(lambda m: create_wiki_link(m.group(1)), content)
        
        # Process Chinese text
        content = self.wrap_chinese(content)
        
        # Handle LLM annotations
        if llm_annotations:
            for pos, annotation in llm_annotations.items():
                content = content[:int(pos)] + "🔍✨💡" + content[int(pos):]
        
        # Process structured blocks
        content = self.process_multiline_blocks(content)
        content = self.process_lists(content)
        content = self.pgn_pattern.sub(common.chess.fen_to_board_old, content)
        content = self.process_colors(content, message, db_session)
        content = self.literal_pattern.sub(lambda m: create_literal_text(m.group(1).strip()), content)
        
        # Handle section breaks
        content = self.section_break_pattern.sub('<hr>', content)
        
        # Wrap plain text in paragraphs
        paragraphs = []
        for para in content.split('\n'):
            if para.strip():
                if not para.strip().startswith('<'):
                    para = f'<p>{para.strip()}</p>'
                paragraphs.append(para.strip())
        
        return '\n'.join(paragraphs)
