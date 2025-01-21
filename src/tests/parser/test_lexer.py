import unittest
from textwrap import dedent
from parser.lexer import tokenize, TokenType, Token, LexerError

class TestAtacamaLexer(unittest.TestCase):
    """Test suite for the Atacama lexer component."""

    def assert_tokens(self, text, expected_types):
        """Helper to verify token sequence types match expectations."""
        tokens = list(tokenize(text))
        actual_types = [t.type for t in tokens]
        self.assertEqual(actual_types, expected_types,
            f"\nExpected: {[t.name for t in expected_types]}"
            f"\nGot: {[t.name for t in actual_types]}")

    def assert_token_values(self, text, expected_tokens):
        """Helper to verify both token types and values."""
        tokens = list(tokenize(text))
        for actual, (exp_type, exp_value) in zip(tokens, expected_tokens):
            self.assertEqual(actual.type, exp_type,
                f"Expected token type {exp_type.name}, got {actual.type.name}")
            self.assertEqual(actual.value, exp_value,
                f"Expected value '{exp_value}', got '{actual.value}'")
        self.assertEqual(len(tokens), len(expected_tokens),
            "Number of tokens doesn't match expected")

    def test_empty_input(self):
        """Lexer should handle empty input gracefully."""
        tokens = list(tokenize(""))
        self.assertEqual(len(tokens), 0)

    def test_plain_text(self):
        """Lexer should tokenize plain text correctly."""
        text = "Hello, world!"
        self.assert_token_values(text, [(TokenType.TEXT, "Hello, world!")])

    def test_whitespace(self):
        """Lexer should handle whitespace appropriately."""
        text = "Hello    world"
        self.assert_token_values(text, [
            (TokenType.TEXT, "Hello    world"),
        ])

    def test_line_color_tags(self):
        """Lexer should properly tokenize color tags at line start."""
        text = "<red>Important warning\nNormal text"
        self.assert_token_values(text, [
            (TokenType.COLOR_BLOCK_TAG, "<red>"),
            (TokenType.TEXT, "Important warning"),
            (TokenType.NEWLINE, "\n"),
            (TokenType.TEXT, "Normal text")
        ])

    def test_parenthesized_color_tags(self):
        """Lexer should handle color tags within parentheses."""
        text = "Note: (<red>important)"
        self.assert_token_values(text, [
            (TokenType.TEXT, "Note: "),
            (TokenType.PARENTHESIS_START, "("),
            (TokenType.COLOR_INLINE_TAG, "<red>"),
            (TokenType.TEXT, "important"),
            (TokenType.PARENTHESIS_END, ")")
        ])

    def test_nested_parentheses(self):
        """Lexer should track nested parentheses correctly."""
        text = "(((<red>deep)))"
        self.assert_token_values(text, [
            (TokenType.PARENTHESIS_START, "("),
            (TokenType.PARENTHESIS_START, "("),
            (TokenType.PARENTHESIS_START, "("),
            (TokenType.COLOR_INLINE_TAG, "<red>"),
            (TokenType.TEXT, "deep"),
            (TokenType.PARENTHESIS_END, ")"),
            (TokenType.PARENTHESIS_END, ")"),
            (TokenType.PARENTHESIS_END, ")")
        ])

    def test_multi_quote_blocks(self):
        """Lexer should properly handle multi-quote blocks."""
        text = dedent("""
            Before
            <<<
            Quoted text
            More quoted
            >>>
            After
        """).strip()
        
        self.assert_tokens(text, [
            TokenType.TEXT,
            TokenType.NEWLINE,
            TokenType.MLQ_START,
            TokenType.NEWLINE,
            TokenType.TEXT,
            TokenType.NEWLINE,
            TokenType.TEXT,
            TokenType.NEWLINE,
            TokenType.MLQ_END,
            TokenType.NEWLINE,
            TokenType.TEXT
        ])

    def test_lists(self):
        """Lexer should recognize different types of list markers at line start."""
        text = dedent("""
            * Bullet item
            # Numbered item
            > Arrow item
        """).strip()
        
        self.assert_tokens(text, [
            TokenType.BULLET_LIST_MARKER, TokenType.WHITESPACE, TokenType.TEXT, TokenType.NEWLINE,
            TokenType.NUMBER_LIST_MARKER, TokenType.WHITESPACE, TokenType.TEXT, TokenType.NEWLINE,
            TokenType.ARROW_LIST_MARKER, TokenType.WHITESPACE, TokenType.TEXT
        ])

    def test_chinese_text(self):
        """Lexer should identify Chinese character sequences."""
        text = "Hello 世界 World"
        self.assert_token_values(text, [
            (TokenType.TEXT, "Hello "),
            (TokenType.CHINESE_TEXT, "世界"),
            (TokenType.TEXT, " World")
        ])

    def test_urls(self):
        """Lexer should properly handle URLs."""
        text = "Visit https://example.com/path?q=1"
        self.assert_token_values(text, [
            (TokenType.TEXT, "Visit "),
            (TokenType.URL, "https://example.com/path?q=1")
        ])

    def test_literal_text(self):
        """Lexer should handle literal text sections."""
        text = "Code: <<print('hello')>>"
        self.assert_token_values(text, [
            (TokenType.TEXT, "Code: "),
            (TokenType.LITERAL_START, "<<"),
            (TokenType.TEXT, "print"),
            (TokenType.PARENTHESIS_START, "("),
            (TokenType.TEXT, "'hello'"),
            (TokenType.PARENTHESIS_END, ")"),
            (TokenType.LITERAL_END, ">>")
        ])

    def test_section_breaks(self):
        """Lexer should recognize section break markers."""
        text = "Section 1\n----\nSection 2"
        self.assert_token_values(text, [
            (TokenType.TEXT, "Section 1"),
            (TokenType.NEWLINE, "\n"),
            (TokenType.SECTION_BREAK, "----"),
            (TokenType.NEWLINE, "\n"),
            (TokenType.TEXT, "Section 2")
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
        """Test a complex document with multiple features interacting."""
        text = dedent("""
            Welcome
            ----
            <red>Important note
            * First item (with <blue>highlight)
            * Second item with 中文
            
            >>> More details <<<
            Visit https://example.com
        """).strip()
        
        tokens = list(tokenize(text))
        # Verify specific important characteristics
        self.assertTrue(any(t.type == TokenType.SECTION_BREAK for t in tokens))
        self.assertTrue(any(t.type == TokenType.COLOR_BLOCK_TAG for t in tokens))
        self.assertTrue(any(t.type == TokenType.COLOR_INLINE_TAG for t in tokens))
        self.assertTrue(any(t.type == TokenType.BULLET_LIST_MARKER for t in tokens))
        self.assertTrue(any(t.type == TokenType.CHINESE_TEXT for t in tokens))
        self.assertTrue(any(t.type == TokenType.URL for t in tokens))

    def test_invalid_color_tags(self):
        """Test handling of invalid or misplaced color tags."""
        # Color tag in middle of line without parentheses
        text = "Start <red>not valid"
        tokens = list(tokenize(text))
        self.assertEqual(len(tokens), 2)  # Should treat as text
        self.assertEqual(tokens[0].type, TokenType.TEXT)

        # Invalid color name
        text = "<invalid>text"
        tokens = list(tokenize(text))
        self.assertEqual(len(tokens), 1)
        self.assertEqual(tokens[0].type, TokenType.TEXT)

if __name__ == '__main__':
    unittest.main()
