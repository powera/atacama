import unittest
from textwrap import dedent

from aml_parser.lexer import tokenize, TokenType, Token, LexerError


class TestAtacamaLexer(unittest.TestCase):
    """Test suite for the Atacama lexer component."""

    def assert_tokens(self, text, expected_types):
        """Helper to verify token sequence types match expectations."""
        tokens = list(tokenize(text))
        actual_types = [t.type for t in tokens]
        self.assertEqual(
            actual_types,
            expected_types,
            f"\nExpected: {[t.name for t in expected_types]}"
            f"\nGot: {[t.name for t in actual_types]}",
        )

    def assert_token_values(self, text, expected_tokens):
        """Helper to verify both token types and values."""
        tokens = list(tokenize(text))
        for actual, (exp_type, exp_value) in zip(tokens, expected_tokens):
            self.assertEqual(
                actual.type,
                exp_type,
                f"Expected token type {exp_type.name}, got {actual.type.name}",
            )
            self.assertEqual(
                actual.value, exp_value, f"Expected value '{exp_value}', got '{actual.value}'"
            )
        self.assertEqual(
            len(tokens), len(expected_tokens), "Number of tokens doesn't match expected"
        )

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
        self.assert_token_values(
            text,
            [
                (TokenType.TEXT, "Hello    world"),
            ],
        )

    def test_line_color_tags(self):
        """Lexer should properly tokenize color tags at line start."""
        text = "<red>Important warning\nNormal text"
        self.assert_token_values(
            text,
            [
                (TokenType.COLOR_TAG, "<red>"),
                (TokenType.TEXT, "Important warning"),
                (TokenType.NEWLINE, "\n"),
                (TokenType.TEXT, "Normal text"),
            ],
        )

    def test_parenthesized_color_tags(self):
        """Lexer should handle color tags within parentheses."""
        text = "Note: (<red>important)"
        self.assert_token_values(
            text,
            [
                (TokenType.TEXT, "Note: "),
                (TokenType.PARENTHESIS_START, "("),
                (TokenType.COLOR_TAG, "<red>"),
                (TokenType.TEXT, "important"),
                (TokenType.PARENTHESIS_END, ")"),
            ],
        )

    def test_nested_parentheses(self):
        """Lexer should track nested parentheses correctly."""
        text = "(((<red>deep)))"
        self.assert_token_values(
            text,
            [
                (TokenType.PARENTHESIS_START, "("),
                (TokenType.PARENTHESIS_START, "("),
                (TokenType.PARENTHESIS_START, "("),
                (TokenType.COLOR_TAG, "<red>"),
                (TokenType.TEXT, "deep"),
                (TokenType.PARENTHESIS_END, ")"),
                (TokenType.PARENTHESIS_END, ")"),
                (TokenType.PARENTHESIS_END, ")"),
            ],
        )

    def test_multi_quote_blocks(self):
        """Lexer should properly handle multi-quote blocks."""
        text = dedent(
            """
            Before
            <<<
            Quoted text
            More quoted
            >>>
            After
        """
        ).strip()

        self.assert_tokens(
            text,
            [
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
                TokenType.TEXT,
            ],
        )

    def test_lists(self):
        """Lexer should recognize different types of list markers at line start."""
        text = dedent(
            """
            * Bullet item
            # Numbered item
            > Arrow item
        """
        ).strip()

        self.assert_tokens(
            text,
            [
                TokenType.BULLET_LIST_MARKER,
                TokenType.TEXT,
                TokenType.NEWLINE,
                TokenType.NUMBER_LIST_MARKER,
                TokenType.TEXT,
                TokenType.NEWLINE,
                TokenType.ARROW_LIST_MARKER,
                TokenType.TEXT,
            ],
        )

    def test_chinese_text(self):
        """Lexer should identify Chinese character sequences."""
        text = "Hello 世界 World"
        self.assert_token_values(
            text,
            [
                (TokenType.TEXT, "Hello "),
                (TokenType.CHINESE_TEXT, "世界"),
                (TokenType.TEXT, " World"),
            ],
        )

    def test_urls(self):
        """Lexer should properly handle URLs."""
        text = "Visit https://example.com/path?q=1"
        self.assert_token_values(
            text, [(TokenType.TEXT, "Visit "), (TokenType.URL, "https://example.com/path?q=1")]
        )

    def test_literal_text(self):
        """Lexer should handle literal text sections."""
        text = "Code: <<print('hello')>>"
        self.assert_token_values(
            text,
            [
                (TokenType.TEXT, "Code: "),
                (TokenType.LITERAL_START, "<<"),
                (TokenType.TEXT, "print"),
                (TokenType.PARENTHESIS_START, "("),
                (TokenType.TEXT, "'hello'"),
                (TokenType.PARENTHESIS_END, ")"),
                (TokenType.LITERAL_END, ">>"),
            ],
        )

    def test_section_breaks(self):
        """Lexer should recognize section break markers."""
        text = "Section 1\n----\nSection 2"
        self.assert_token_values(
            text,
            [
                (TokenType.TEXT, "Section 1"),
                (TokenType.NEWLINE, "\n"),
                (TokenType.SECTION_BREAK, "----"),
                (TokenType.NEWLINE, "\n"),
                (TokenType.TEXT, "Section 2"),
            ],
        )

    def test_more_tag(self):
        """Lexer should recognize --MORE-- tags."""
        text = "Before\n--MORE--\nAfter"
        self.assert_token_values(
            text,
            [
                (TokenType.TEXT, "Before"),
                (TokenType.NEWLINE, "\n"),
                (TokenType.MORE_TAG, "--MORE--"),
                (TokenType.NEWLINE, "\n"),
                (TokenType.TEXT, "After"),
            ],
        )

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
        text = dedent(
            """
            Welcome
            ----
            <red>Important note
            * First item (with <blue>highlight)
            * Second item with 中文
            
            >>> More details <<<
            Visit https://example.com
        """
        ).strip()

        tokens = list(tokenize(text))
        # Verify specific important characteristics
        self.assertTrue(any(t.type == TokenType.SECTION_BREAK for t in tokens))
        self.assertTrue(any(t.type == TokenType.COLOR_TAG for t in tokens))
        self.assertTrue(any(t.type == TokenType.BULLET_LIST_MARKER for t in tokens))
        self.assertTrue(any(t.type == TokenType.CHINESE_TEXT for t in tokens))
        self.assertTrue(any(t.type == TokenType.URL for t in tokens))

    def test_invalid_color_tags(self):
        """Test handling of invalid or misplaced color tags."""
        # Color tag in middle of line not processed, but still lexed as tag
        text = "Start <red>not valid"
        tokens = list(tokenize(text))
        self.assertEqual(len(tokens), 3)
        self.assertEqual(tokens[0].type, TokenType.TEXT)
        self.assertEqual(tokens[1].type, TokenType.COLOR_TAG)

        # Invalid color name
        text = "<invalid>text"
        tokens = list(tokenize(text))
        self.assertEqual(len(tokens), 1)
        self.assertEqual(tokens[0].type, TokenType.TEXT)

    def test_colored_multi_quote_blocks(self):
        """Lexer should handle color-prefixed MLQ blocks."""
        text = dedent(
            """
            Before
            <red> <<<
            Quoted text
            More quoted
            >>>
            After
        """
        ).strip()

        tokens = list(tokenize(text))

        # Verify the overall token sequence is correct
        self.assert_tokens(
            text,
            [
                TokenType.TEXT,
                TokenType.NEWLINE,
                TokenType.COLOR_TAG,  # The lexer phase does not handle any logic.
                TokenType.TEXT,  # Whitespace
                TokenType.MLQ_START,
                TokenType.NEWLINE,
                TokenType.TEXT,
                TokenType.NEWLINE,
                TokenType.TEXT,
                TokenType.NEWLINE,
                TokenType.MLQ_END,
                TokenType.NEWLINE,
                TokenType.TEXT,
            ],
        )

    def test_invalid_tag_soup(self):
        """Lexer should not worry about invalid tags"""
        text = dedent(
            """
            Before
            <red> <<< #] #] (((
            Quoted text
        """
        ).strip()

        tokens = list(tokenize(text))

        # Verify the overall token sequence is correct
        self.assert_tokens(
            text,
            [
                TokenType.TEXT,
                TokenType.NEWLINE,
                TokenType.COLOR_TAG,
                TokenType.TEXT,  # Whitespace
                TokenType.MLQ_START,
                TokenType.TEXT,  # Whitespace
                TokenType.TITLE_END,
                TokenType.TEXT,  # Whitespace
                TokenType.TITLE_END,
                TokenType.TEXT,  # Whitespace
                TokenType.PARENTHESIS_START,
                TokenType.PARENTHESIS_START,
                TokenType.PARENTHESIS_START,
                TokenType.NEWLINE,
                TokenType.TEXT,
            ],
        )

    def test_templates_basic(self):
        """Lexer should tokenize templates correctly."""
        text = "Book: {{isbn|1234567890}}"
        self.assert_token_values(
            text, [(TokenType.TEXT, "Book: "), (TokenType.TEMPLATE, "1234567890")]
        )
        # Verify template name
        tokens = list(tokenize(text))
        self.assertEqual(tokens[1].template_name, "isbn")

    def test_templates_wikidata(self):
        """Lexer should handle wikidata template."""
        text = "Entity: {{wikidata|Q12345}}"
        self.assert_token_values(
            text, [(TokenType.TEXT, "Entity: "), (TokenType.TEMPLATE, "Q12345")]
        )
        tokens = list(tokenize(text))
        self.assertEqual(tokens[1].template_name, "wikidata")

    def test_templates_nested_braces(self):
        """Lexer should handle templates with nested braces."""
        text = "{{pgn|{{nested}}}}"
        tokens = list(tokenize(text))
        self.assertEqual(len(tokens), 1)
        self.assertEqual(tokens[0].type, TokenType.TEMPLATE)
        self.assertEqual(tokens[0].value, "{{nested}}")
        self.assertEqual(tokens[0].template_name, "pgn")

    def test_templates_invalid_no_pipe(self):
        """Lexer should not tokenize template without pipe as template."""
        text = "{{notatemplate}}"
        tokens = list(tokenize(text))
        # Should become text since no pipe separator
        self.assertTrue(all(t.type == TokenType.TEXT for t in tokens))

    def test_templates_unclosed(self):
        """Lexer should handle unclosed templates gracefully."""
        text = "{{isbn|unclosed"
        tokens = list(tokenize(text))
        # Should become text
        self.assertTrue(all(t.type == TokenType.TEXT for t in tokens))

    def test_title_tags(self):
        """Lexer should tokenize title tags correctly."""
        text = "[# Section Title #]"
        self.assert_token_values(
            text,
            [
                (TokenType.TITLE_START, "[#"),
                (TokenType.TEXT, " Section Title "),
                (TokenType.TITLE_END, "#]"),
            ],
        )

    def test_title_with_formatting(self):
        """Lexer should handle title with inner formatting."""
        text = "[# *Emphasized* Title #]"
        self.assert_tokens(
            text,
            [
                TokenType.TITLE_START,
                TokenType.TEXT,  # space
                TokenType.EMPHASIS,
                TokenType.TEXT,
                TokenType.TITLE_END,
            ],
        )

    def test_wikilinks(self):
        """Lexer should tokenize wikilinks correctly."""
        text = "See [[Article Name]] for info"
        self.assert_token_values(
            text,
            [
                (TokenType.TEXT, "See "),
                (TokenType.WIKILINK_START, "[["),
                (TokenType.TEXT, "Article Name"),
                (TokenType.WIKILINK_END, "]]"),
                (TokenType.TEXT, " for info"),
            ],
        )

    def test_wikilink_unclosed(self):
        """Lexer should handle unclosed wikilinks."""
        text = "See [[Unclosed"
        tokens = list(tokenize(text))
        # Should have start marker but no end
        has_start = any(t.type == TokenType.WIKILINK_START for t in tokens)
        has_end = any(t.type == TokenType.WIKILINK_END for t in tokens)
        self.assertTrue(has_start)
        self.assertFalse(has_end)

    def test_emphasis_basic(self):
        """Lexer should tokenize basic emphasis correctly."""
        text = "This is *emphasized* text"
        self.assert_token_values(
            text,
            [
                (TokenType.TEXT, "This is "),
                (TokenType.EMPHASIS, "emphasized"),
                (TokenType.TEXT, " text"),
            ],
        )

    def test_emphasis_at_start(self):
        """Lexer should handle emphasis at start of text."""
        text = "*start* of line"
        tokens = list(tokenize(text))
        self.assertEqual(tokens[0].type, TokenType.EMPHASIS)
        self.assertEqual(tokens[0].value, "start")

    def test_emphasis_at_end(self):
        """Lexer should handle emphasis at end of text."""
        text = "end of *line*"
        tokens = list(tokenize(text))
        self.assertEqual(tokens[-1].type, TokenType.EMPHASIS)
        self.assertEqual(tokens[-1].value, "line")

    def test_emphasis_with_punctuation(self):
        """Lexer should handle emphasis with punctuation inside."""
        text = "Say *hello, world!* today"
        tokens = list(tokenize(text))
        emphasis_tokens = [t for t in tokens if t.type == TokenType.EMPHASIS]
        self.assertEqual(len(emphasis_tokens), 1)
        self.assertEqual(emphasis_tokens[0].value, "hello, world!")

    def test_emphasis_max_length(self):
        """Lexer should accept emphasis up to 40 characters."""
        # Exactly 40 chars should work
        text = "*" + "x" * 40 + "*"
        tokens = list(tokenize(text))
        self.assertEqual(len(tokens), 1)
        self.assertEqual(tokens[0].type, TokenType.EMPHASIS)
        self.assertEqual(len(tokens[0].value), 40)

    def test_emphasis_boundary_cases(self):
        """Lexer should handle emphasis edge cases."""
        # Asterisk with space after - not emphasis, becomes list marker at line start
        text = "* bullet item"
        tokens = list(tokenize(text))
        self.assertEqual(tokens[0].type, TokenType.BULLET_LIST_MARKER)

        # Asterisk mid-word without closing asterisk - splits into text tokens
        # This is because the lexer sees *3 as potential emphasis start, but
        # with no closing *, it backtracks and outputs * as separate text
        text = "2*3=6"
        tokens = list(tokenize(text))
        self.assertTrue(all(t.type == TokenType.TEXT for t in tokens))
        # Should have 3 tokens: "2", "*", "3=6"
        self.assertEqual(len(tokens), 3)

        # Too long emphasis (over 40 chars) - not tokenized as emphasis
        text = "*" + "x" * 41 + "*"
        tokens = list(tokenize(text))
        self.assertTrue(all(t.type == TokenType.TEXT for t in tokens))

    def test_url_with_fragment(self):
        """Lexer should handle URLs with fragments."""
        text = "Link: https://example.com/page#section"
        self.assert_token_values(
            text, [(TokenType.TEXT, "Link: "), (TokenType.URL, "https://example.com/page#section")]
        )

    def test_url_http(self):
        """Lexer should handle http URLs."""
        text = "Visit http://example.com"
        self.assert_token_values(
            text, [(TokenType.TEXT, "Visit "), (TokenType.URL, "http://example.com")]
        )

    def test_url_complex_query(self):
        """Lexer should handle URLs with complex query strings."""
        text = "API: https://api.example.com/v1?foo=bar&baz=qux"
        tokens = list(tokenize(text))
        self.assertEqual(tokens[1].type, TokenType.URL)
        self.assertIn("foo=bar", tokens[1].value)
        self.assertIn("baz=qux", tokens[1].value)

    def test_lexer_error_class(self):
        """LexerError should have line and column info."""
        error = LexerError("Test error", line=5, column=10)
        self.assertEqual(error.message, "Test error")
        self.assertEqual(error.line, 5)
        self.assertEqual(error.column, 10)
        self.assertIn("line 5", str(error))
        self.assertIn("column 10", str(error))


if __name__ == "__main__":
    unittest.main()
