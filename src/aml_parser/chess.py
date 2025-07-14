"""Chess board processing and rendering functionality."""

import re
from typing import Dict, Match, Tuple, Optional

def get_piece_map() -> Dict[str, str]:
    """Get mapping of FEN piece letters to Unicode chess pieces."""
    return {
        'k': '♔', 'q': '♕', 'r': '♖', 'b': '♗', 'n': '♘', 'p': '♙',  # White pieces
        'K': '♚', 'Q': '♛', 'R': '♜', 'B': '♝', 'N': '♞', 'P': '♟',  # Black pieces
    }

def validate_fen(fen: str) -> Tuple[bool, Optional[str]]:
    """
    Validate a FEN string for basic correctness.
    
    :param fen: FEN string to validate
    :return: Tuple of (is_valid, error_message)
    """
    parts = fen.split()
    if len(parts) < 1:
        return False, "Empty FEN string"
        
    position = parts[0]
    ranks = position.split('/')
    
    if len(ranks) != 8:
        return False, "FEN must have 8 ranks"
        
    for rank in ranks:
        file_count = 0
        for char in rank:
            if char.isdigit():
                file_count += int(char)
            elif char in 'kqrbnpKQRBNP':
                file_count += 1
            else:
                return False, f"Invalid character in FEN: {char}"
        if file_count != 8:
            return False, "Each rank must have 8 squares"
            
    return True, None

def fen_to_board(fen: str) -> str:
    """
    Convert FEN chess position notation into HTML board representation.
    
    :param fen: FEN string representing the chess position
    :return: HTML string representing the chess board
    """
    # Validate FEN
    is_valid, error = validate_fen(fen)
    if not is_valid:
        # Return plain text representation if invalid
        return f'<pre class="invalid-pgn">Invalid chess position: {error}\nInput: {fen}</pre>'
    
    fen_parts = fen.split()
    position = fen_parts[0]
    to_move = 'white' if len(fen_parts) > 1 and fen_parts[1] == 'w' else 'black'

    board = []
    ranks = position.split('/')  # Get just the piece positions
    pieces = get_piece_map()
    
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

    # Add clickable FEN display
    board_html.append('<div class="chess-fen">')
    board_html.append(f'<button type="button" class="fen-toggle" aria-label="Show FEN">')
    board_html.append('Show position (FEN)')
    board_html.append('</button>')
    board_html.append(f'<pre class="fen-text" style="display: none">{fen}</pre>')
    board_html.append('</div>')
    
    board_html.append('</div>')
    return '\n'.join(board_html)

def fen_to_board_old(match: Match) -> str:
    """
    Legacy wrapper for regex match-based FEN processing.
    
    :param match: Regex match object containing FEN string
    :return: HTML string representing the chess board
    """
    return fen_to_board(match.group(1))
