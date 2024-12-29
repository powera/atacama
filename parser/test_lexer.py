import unittest
from textwrap import dedent
from parser.lexer import tokenize, TokenType, Token, LexerError

class TestLexer(unittest.TestCase):
    """Test suite for the Atacama lexer component."""

    def assert_tokens(self, text, expected_types):
        """Helper to verify token sequence types match expectations."""
        tokens = list(tokenize(text))
        actual_types = [t.type for t in tokens]
        self.assertEqual(actual_types, expected_types,
            f"\nExpected: {[t.name for t in expected_types]}"
            f"\nGot: {[t.name for t in actual_types]}")

    def test_empty_input(self):
        """Lexer should handle empty input gracefully."""
        tokens = list(tokenize(""))
        self.assertEqual(len(tokens), 0)

    def test_plain_text(self):
        """Lexer should tokenize plain text correctly."""
        text = "Hello, world!"
        tokens = list(tokenize(text))
        self.assertEqual(len(tokens), 1)
        self.assertEqual(tokens[0].type, TokenType.TEXT)
        self.assertEqual(tokens[0].value, text)

    def test_color_blocks(self):
        """Lexer should properly tokenize color block tags."""
        text = "<red>Important warning"
        self.assert_tokens(text, [
            TokenType.COLOR_BLOCK_START,
            TokenType.TEXT
        ])

    def test_nested_colors(self):
        """Lexer should handle nested color tags in parentheses."""
        text = "Note: (<red>important)"
        self.assert_tokens(text, [
            TokenType.TEXT,
            TokenType.COLOR_INLINE_START,
            TokenType.TEXT,
        ])

    def test_lists(self):
        """Lexer should recognize different types of list markers."""
        text = dedent("""
            * Bullet item
            # Numbered item
            > Arrow item
        """).strip()
        
        self.assert_tokens(text, [
            TokenType.BULLET_LIST_MARKER, TokenType.TEXT, TokenType.NEWLINE,
            TokenType.NUMBER_LIST_MARKER, TokenType.TEXT, TokenType.NEWLINE,
            TokenType.ARROW_LIST_MARKER, TokenType.TEXT
        ])

    def test_chinese_text(self):
        """Lexer should identify Chinese character sequences."""
        text = "Hello 世界 World"
        self.assert_tokens(text, [
            TokenType.TEXT,
            TokenType.CHINESE_TEXT,
            TokenType.TEXT
        ])

    def test_urls_and_wikilinks(self):
        """Lexer should properly handle URLs and wikilinks."""
        text = "Visit https://example.com and [[Wikipedia]]"
        self.assert_tokens(text, [
            TokenType.TEXT,
            TokenType.URL,
            TokenType.TEXT,
            TokenType.WIKILINK_START,
            TokenType.TEXT,
            TokenType.WIKILINK_END
        ])

    def test_literal_text(self):
        """Lexer should handle literal text sections."""
        text = "Code: <<print('hello')>>"
        self.assert_tokens(text, [
            TokenType.TEXT,
            TokenType.LITERAL_START,
            TokenType.TEXT,
            TokenType.LITERAL_END
        ])

    def test_section_breaks(self):
        """Lexer should recognize section break markers."""
        text = "Section 1\n----\nSection 2"
        self.assert_tokens(text, [
            TokenType.TEXT,
            TokenType.NEWLINE,
            TokenType.SECTION_BREAK,
            TokenType.NEWLINE,
            TokenType.TEXT
        ])

    def test_position_tracking(self):
        """Lexer should track line and column numbers accurately."""
        text = "Line 1\nLine 2"
        tokens = list(tokenize(text))
        
        self.assertEqual(tokens[0].line, 1)
        self.assertEqual(tokens[0].column, 1)
        self.assertEqual(tokens[2].line, 2)
        self.assertEqual(tokens[2].column, 1)

    def test_complex_document(self):
        """Test a more complex document with multiple features."""
        text = dedent("""
            Welcome to my notes
            
            <red>Important points:</red>
            * First item with 中文
            * Second item with [[Wiki]]
            
            Visit https://example.com for more.
            ----
            That's all!
        """).strip()
        
        # We don't check exact tokens here, but verify no lexer errors
        tokens = list(tokenize(text))
        self.assertTrue(len(tokens) > 10)  # Should have multiple tokens

if __name__ == '__main__':
    unittest.main()
