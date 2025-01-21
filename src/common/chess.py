"""Chess board processing and rendering functionality."""

from typing import Dict, Match

def get_piece_map() -> Dict[str, str]:
    """Get mapping of FEN piece letters to Unicode chess pieces."""
    return {
        'k': '♔', 'q': '♕', 'r': '♖', 'b': '♗', 'n': '♘', 'p': '♙',  # White pieces
        'K': '♚', 'Q': '♛', 'R': '♜', 'B': '♝', 'N': '♞', 'P': '♟',  # Black pieces
    }

def fen_to_board(match: Match) -> str:
    """
    Convert FEN chess position notation into HTML board representation.
    
    :param match: Regex match object containing FEN string
    :return: HTML string representing the chess board
    """
    fen = match.group(1)
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
    
    board_html.append('</div>')
    return '\n'.join(board_html)
