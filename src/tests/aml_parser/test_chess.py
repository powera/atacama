"""Tests for the chess module FEN parsing and board rendering."""

import sys
import unittest
from unittest.mock import MagicMock

# Import chess module directly to avoid aml_parser.__init__.py dependencies
# This allows the tests to run without sqlalchemy being installed
import importlib.util
spec = importlib.util.spec_from_file_location(
    "chess",
    "src/aml_parser/chess.py"
)
chess_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(chess_module)

get_piece_map = chess_module.get_piece_map
validate_fen = chess_module.validate_fen
fen_to_board = chess_module.fen_to_board
fen_to_board_old = chess_module.fen_to_board_old


class TestGetPieceMap(unittest.TestCase):
    """Test suite for get_piece_map function."""

    def test_returns_dict(self):
        """get_piece_map should return a dictionary."""
        result = get_piece_map()
        self.assertIsInstance(result, dict)

    def test_contains_all_pieces(self):
        """get_piece_map should contain all 12 chess pieces."""
        result = get_piece_map()
        # 6 white pieces + 6 black pieces
        self.assertEqual(len(result), 12)

    def test_white_pieces_lowercase(self):
        """White pieces should use lowercase letters."""
        result = get_piece_map()
        white_pieces = ['k', 'q', 'r', 'b', 'n', 'p']
        for piece in white_pieces:
            self.assertIn(piece, result)

    def test_black_pieces_uppercase(self):
        """Black pieces should use uppercase letters."""
        result = get_piece_map()
        black_pieces = ['K', 'Q', 'R', 'B', 'N', 'P']
        for piece in black_pieces:
            self.assertIn(piece, result)

    def test_unicode_symbols_correct(self):
        """Piece symbols should be correct Unicode chess pieces."""
        result = get_piece_map()
        # White pieces (lowercase in FEN)
        self.assertEqual(result['k'], '\u2654')  # White King
        self.assertEqual(result['q'], '\u2655')  # White Queen
        self.assertEqual(result['r'], '\u2656')  # White Rook
        self.assertEqual(result['b'], '\u2657')  # White Bishop
        self.assertEqual(result['n'], '\u2658')  # White Knight
        self.assertEqual(result['p'], '\u2659')  # White Pawn
        # Black pieces (uppercase in FEN)
        self.assertEqual(result['K'], '\u265a')  # Black King
        self.assertEqual(result['Q'], '\u265b')  # Black Queen
        self.assertEqual(result['R'], '\u265c')  # Black Rook
        self.assertEqual(result['B'], '\u265d')  # Black Bishop
        self.assertEqual(result['N'], '\u265e')  # Black Knight
        self.assertEqual(result['P'], '\u265f')  # Black Pawn


class TestValidateFen(unittest.TestCase):
    """Test suite for validate_fen function."""

    def test_valid_starting_position(self):
        """Starting position FEN should be valid."""
        fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
        is_valid, error = validate_fen(fen)
        self.assertTrue(is_valid)
        self.assertIsNone(error)

    def test_valid_position_only(self):
        """Position-only FEN should be valid."""
        fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR"
        is_valid, error = validate_fen(fen)
        self.assertTrue(is_valid)
        self.assertIsNone(error)

    def test_valid_midgame_position(self):
        """Midgame position FEN should be valid."""
        fen = "r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4"
        is_valid, error = validate_fen(fen)
        self.assertTrue(is_valid)
        self.assertIsNone(error)

    def test_valid_empty_board(self):
        """Empty board FEN should be valid."""
        fen = "8/8/8/8/8/8/8/8"
        is_valid, error = validate_fen(fen)
        self.assertTrue(is_valid)
        self.assertIsNone(error)

    def test_invalid_empty_string(self):
        """Empty string should be invalid."""
        fen = ""
        is_valid, error = validate_fen(fen)
        self.assertFalse(is_valid)
        self.assertEqual(error, "Empty FEN string")

    def test_invalid_too_few_ranks(self):
        """FEN with fewer than 8 ranks should be invalid."""
        fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP"  # Only 7 ranks
        is_valid, error = validate_fen(fen)
        self.assertFalse(is_valid)
        self.assertEqual(error, "FEN must have 8 ranks")

    def test_invalid_too_many_ranks(self):
        """FEN with more than 8 ranks should be invalid."""
        fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR/8"  # 9 ranks
        is_valid, error = validate_fen(fen)
        self.assertFalse(is_valid)
        self.assertEqual(error, "FEN must have 8 ranks")

    def test_invalid_too_few_files_in_rank(self):
        """FEN with fewer than 8 files in a rank should be invalid."""
        fen = "rnbqkbn/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR"  # First rank has 7 squares
        is_valid, error = validate_fen(fen)
        self.assertFalse(is_valid)
        self.assertEqual(error, "Each rank must have 8 squares")

    def test_invalid_too_many_files_in_rank(self):
        """FEN with more than 8 files in a rank should be invalid."""
        fen = "rnbqkbnrr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR"  # First rank has 9 squares
        is_valid, error = validate_fen(fen)
        self.assertFalse(is_valid)
        self.assertEqual(error, "Each rank must have 8 squares")

    def test_invalid_character_in_fen(self):
        """FEN with invalid character should be invalid."""
        fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBXKBNR"  # X is invalid
        is_valid, error = validate_fen(fen)
        self.assertFalse(is_valid)
        self.assertIn("Invalid character in FEN", error)

    def test_valid_with_numbers_and_pieces_mixed(self):
        """FEN with mixed numbers and pieces should be valid if total is 8."""
        fen = "r1b1k2r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R"
        is_valid, error = validate_fen(fen)
        self.assertTrue(is_valid)
        self.assertIsNone(error)


class TestFenToBoard(unittest.TestCase):
    """Test suite for fen_to_board function."""

    def test_invalid_fen_returns_error_html(self):
        """Invalid FEN should return error HTML."""
        fen = "invalid"
        result = fen_to_board(fen)
        self.assertIn('class="invalid-pgn"', result)
        self.assertIn('Invalid chess position', result)

    def test_valid_fen_returns_board_html(self):
        """Valid FEN should return board HTML."""
        fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
        result = fen_to_board(fen)
        self.assertIn('class="chess-board"', result)

    def test_board_contains_turn_indicator(self):
        """Board should contain turn indicator."""
        fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
        result = fen_to_board(fen)
        self.assertIn('class="chess-turn-indicator', result)

    def test_white_to_move(self):
        """Board should show white to move when 'w' in FEN."""
        fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
        result = fen_to_board(fen)
        self.assertIn('white-to-move', result)
        self.assertIn('White to move', result)

    def test_black_to_move(self):
        """Board should show black to move when 'b' in FEN."""
        fen = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1"
        result = fen_to_board(fen)
        self.assertIn('black-to-move', result)
        self.assertIn('Black to move', result)

    def test_board_contains_file_labels(self):
        """Board should contain file labels (a-h)."""
        fen = "8/8/8/8/8/8/8/8"
        result = fen_to_board(fen)
        for file_label in 'abcdefgh':
            self.assertIn(f'>{file_label}</div>', result)

    def test_board_contains_rank_labels(self):
        """Board should contain rank labels (1-8)."""
        fen = "8/8/8/8/8/8/8/8"
        result = fen_to_board(fen)
        for rank_label in range(1, 9):
            self.assertIn(f'>{rank_label}</div>', result)

    def test_board_contains_fen_display(self):
        """Board should contain FEN display button and text."""
        fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
        result = fen_to_board(fen)
        self.assertIn('class="chess-fen"', result)
        self.assertIn('class="fen-toggle"', result)
        self.assertIn('class="fen-text"', result)
        self.assertIn('Show position (FEN)', result)

    def test_board_contains_pieces(self):
        """Board should contain chess pieces."""
        fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
        result = fen_to_board(fen)
        pieces = get_piece_map()
        # Check that at least some pieces are in the HTML
        self.assertIn(pieces['r'], result)  # White rook
        self.assertIn(pieces['R'], result)  # Black rook

    def test_board_cell_colors_alternate(self):
        """Board cells should alternate between light and dark."""
        fen = "8/8/8/8/8/8/8/8"
        result = fen_to_board(fen)
        self.assertIn('class="chess-cell light"', result)
        self.assertIn('class="chess-cell dark"', result)

    def test_piece_colors_correct(self):
        """White and black pieces should have correct piece classes."""
        fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR"
        result = fen_to_board(fen)
        self.assertIn('class="chess-piece white-piece"', result)
        self.assertIn('class="chess-piece black-piece"', result)

    def test_position_only_defaults_to_black(self):
        """Position-only FEN should default to black to move."""
        fen = "8/8/8/8/8/8/8/8"  # No side to move specified
        result = fen_to_board(fen)
        self.assertIn('black-to-move', result)


class TestFenToBoardOld(unittest.TestCase):
    """Test suite for fen_to_board_old function."""

    def test_extracts_fen_from_match(self):
        """fen_to_board_old should extract FEN from regex match group 1."""
        mock_match = MagicMock()
        mock_match.group.return_value = "8/8/8/8/8/8/8/8"

        result = fen_to_board_old(mock_match)

        mock_match.group.assert_called_once_with(1)
        self.assertIn('class="chess-board"', result)

    def test_invalid_fen_from_match(self):
        """fen_to_board_old should handle invalid FEN from match."""
        mock_match = MagicMock()
        mock_match.group.return_value = "invalid"

        result = fen_to_board_old(mock_match)

        self.assertIn('class="invalid-pgn"', result)


if __name__ == '__main__':
    unittest.main()
