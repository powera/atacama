"""Tests for the colorblocks module HTML generation functions."""

import unittest
from unittest.mock import patch, MagicMock

from aml_parser.colorblocks import (
    COLORS,
    create_color_block,
    create_chinese_annotation,
    create_list_item,
    create_list_container,
    create_multiline_block,
    create_literal_text,
    _detect_youtube_url,
    create_url_link,
    create_wiki_link,
    create_emphasis,
    create_inline_title,
    create_template_html,
)


class TestColorsConstant(unittest.TestCase):
    """Test suite for COLORS constant."""

    def test_colors_is_dict(self):
        """COLORS should be a dictionary."""
        self.assertIsInstance(COLORS, dict)

    def test_colors_has_expected_keys(self):
        """COLORS should have expected color keys."""
        expected_colors = [
            "xantham",
            "red",
            "orange",
            "yellow",
            "quote",
            "green",
            "acronym",
            "context",
            "resource",
            "teal",
            "blue",
            "violet",
            "music",
            "mogue",
            "gray",
            "hazel",
        ]
        for color in expected_colors:
            self.assertIn(color, COLORS)

    def test_color_values_are_tuples(self):
        """Each color value should be a tuple of (sigil, css_class, description)."""
        for color, value in COLORS.items():
            self.assertIsInstance(value, tuple)
            self.assertEqual(len(value), 3)


class TestCreateColorBlock(unittest.TestCase):
    """Test suite for create_color_block function."""

    def test_valid_color(self):
        """create_color_block should create proper HTML for valid color."""
        result = create_color_block("red", "test content")
        self.assertIn('class="colorblock color-red"', result)
        self.assertIn('class="sigil"', result)
        self.assertIn('class="colortext-content"', result)
        self.assertIn("test content", result)

    def test_unknown_color_returns_content(self):
        """create_color_block should return content as-is for unknown color."""
        result = create_color_block("unknown", "test content")
        self.assertEqual(result, "test content")

    def test_includes_sigil(self):
        """create_color_block should include the correct sigil."""
        result = create_color_block("red", "content")
        self.assertIn(COLORS["red"][0], result)  # Check sigil

    def test_line_level_vs_inline(self):
        """create_color_block should handle is_line parameter."""
        # Line level
        line_result = create_color_block("red", "content", is_line=True)
        # Inline
        inline_result = create_color_block("red", "content", is_line=False)
        # Both should produce valid HTML with the color
        self.assertIn("color-red", line_result)
        self.assertIn("color-red", inline_result)


class TestCreateChineseAnnotation(unittest.TestCase):
    """Test suite for create_chinese_annotation function."""

    def _setup_mock_module(self, mock_annotation=None, side_effect=None):
        """Helper to set up the aml_parser and pinyin mocks in sys.modules."""
        import sys
        import types

        # Create mock pinyin module
        mock_pinyin = MagicMock()
        if side_effect:
            mock_pinyin.default_processor.get_annotation.side_effect = side_effect
        else:
            mock_pinyin.default_processor.get_annotation.return_value = mock_annotation

        # Create mock aml_parser package
        mock_aml_parser = types.ModuleType("aml_parser")
        mock_aml_parser.pinyin = mock_pinyin

        return {"aml_parser": mock_aml_parser, "aml_parser.pinyin": mock_pinyin}

    def test_creates_span_with_class(self):
        """create_chinese_annotation should create span with annotated-chinese class."""
        mock_annotation = MagicMock()
        mock_annotation.pinyin = "NǏ HǍO"
        mock_annotation.definition = "hello"

        with patch.dict("sys.modules", self._setup_mock_module(mock_annotation)):
            result = create_chinese_annotation("你好")
        self.assertIn('class="annotated-chinese"', result)
        self.assertIn("你好</span>", result)

    def test_includes_data_attributes(self):
        """create_chinese_annotation should include data-pinyin and data-definition."""
        mock_annotation = MagicMock()
        mock_annotation.pinyin = "HǍO"
        mock_annotation.definition = "good"

        with patch.dict("sys.modules", self._setup_mock_module(mock_annotation)):
            result = create_chinese_annotation("好")
        self.assertIn('data-pinyin="HǍO"', result)
        self.assertIn('data-definition="good"', result)

    def test_handles_missing_pinyin(self):
        """create_chinese_annotation should handle None pinyin."""
        mock_annotation = MagicMock()
        mock_annotation.pinyin = None
        mock_annotation.definition = "test"

        with patch.dict("sys.modules", self._setup_mock_module(mock_annotation)):
            result = create_chinese_annotation("好")
        self.assertNotIn("data-pinyin", result)
        self.assertIn('data-definition="test"', result)

    def test_handles_missing_definition(self):
        """create_chinese_annotation should handle None definition."""
        mock_annotation = MagicMock()
        mock_annotation.pinyin = "HǍO"
        mock_annotation.definition = None

        with patch.dict("sys.modules", self._setup_mock_module(mock_annotation)):
            result = create_chinese_annotation("好")
        self.assertIn('data-pinyin="HǍO"', result)
        self.assertNotIn("data-definition", result)

    def test_handles_import_error(self):
        """create_chinese_annotation should handle import error gracefully."""
        # By not mocking anything, the import will fail,
        # which tests the ImportError path
        # The function should return fallback HTML
        result = create_chinese_annotation("好")
        self.assertIn('class="annotated-chinese"', result)
        # Either pinyin-module-missing or annotation-failed is acceptable
        self.assertTrue("data-error=" in result or "data-pinyin" not in result)

    def test_handles_annotation_exception(self):
        """create_chinese_annotation should handle annotation exceptions."""
        with patch.dict(
            "sys.modules", self._setup_mock_module(side_effect=RuntimeError("Test error"))
        ):
            result = create_chinese_annotation("好")
        self.assertIn('class="annotated-chinese"', result)
        self.assertIn('data-error="annotation-failed"', result)


class TestCreateListItem(unittest.TestCase):
    """Test suite for create_list_item function."""

    def test_bullet_list(self):
        """create_list_item should create bullet list item."""
        result = create_list_item("Item content", "bullet")
        self.assertEqual(result, '<li class="bullet-list">Item content</li>')

    def test_number_list(self):
        """create_list_item should create number list item."""
        result = create_list_item("Item content", "number")
        self.assertEqual(result, '<li class="number-list">Item content</li>')

    def test_arrow_list(self):
        """create_list_item should create arrow list item."""
        result = create_list_item("Item content", "arrow")
        self.assertEqual(result, '<li class="arrow-list">Item content</li>')


class TestCreateListContainer(unittest.TestCase):
    """Test suite for create_list_container function."""

    def test_wraps_items_in_ul(self):
        """create_list_container should wrap items in ul tag."""
        items = ["<li>Item 1</li>", "<li>Item 2</li>"]
        result = create_list_container(items)
        self.assertTrue(result.startswith("<ul>"))
        self.assertTrue(result.endswith("</ul>"))
        self.assertIn("<li>Item 1</li>", result)
        self.assertIn("<li>Item 2</li>", result)

    def test_empty_list_returns_empty(self):
        """create_list_container should return empty string for empty list."""
        result = create_list_container([])
        self.assertEqual(result, "")

    def test_single_item(self):
        """create_list_container should handle single item."""
        result = create_list_container(["<li>Only item</li>"])
        self.assertIn("<li>Only item</li>", result)


class TestCreateMultilineBlock(unittest.TestCase):
    """Test suite for create_multiline_block function."""

    def test_basic_mlq(self):
        """create_multiline_block should create basic MLQ HTML."""
        result = create_multiline_block(["Para 1", "Para 2"])
        self.assertIn('class="mlq"', result)
        self.assertIn('class="mlq-collapse"', result)
        self.assertIn('class="mlq-content"', result)
        self.assertIn("<p>Para 1</p>", result)
        self.assertIn("<p>Para 2</p>", result)

    def test_colored_mlq(self):
        """create_multiline_block should handle color parameter."""
        result = create_multiline_block(["Content"], color="red")
        self.assertIn('class="mlq color-red"', result)
        # Should use color sigil
        self.assertIn(COLORS["red"][0], result)

    def test_empty_paragraphs_filtered(self):
        """create_multiline_block should filter empty paragraphs."""
        result = create_multiline_block(["Para", "", "   ", "Another"])
        # Count <p> tags - should only be 2
        self.assertEqual(result.count("<p>"), 2)

    def test_default_sigil(self):
        """create_multiline_block should use '-' as default sigil."""
        result = create_multiline_block(["Content"])
        self.assertIn(">-</span>", result)


class TestCreateLiteralText(unittest.TestCase):
    """Test suite for create_literal_text function."""

    def test_creates_literal_span(self):
        """create_literal_text should create span with literal-text class."""
        result = create_literal_text("code here")
        self.assertEqual(result, '<span class="literal-text">code here</span>')

    def test_strips_whitespace(self):
        """create_literal_text should strip whitespace from content."""
        result = create_literal_text("  code  ")
        self.assertEqual(result, '<span class="literal-text">code</span>')


class TestDetectYoutubeUrl(unittest.TestCase):
    """Test suite for _detect_youtube_url function."""

    def test_standard_youtube_url(self):
        """_detect_youtube_url should detect standard youtube.com URL."""
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        is_youtube, video_id = _detect_youtube_url(url)
        self.assertTrue(is_youtube)
        self.assertEqual(video_id, "dQw4w9WgXcQ")

    def test_short_youtube_url(self):
        """_detect_youtube_url should detect short youtu.be URL."""
        url = "https://youtu.be/dQw4w9WgXcQ"
        is_youtube, video_id = _detect_youtube_url(url)
        self.assertTrue(is_youtube)
        self.assertEqual(video_id, "dQw4w9WgXcQ")

    def test_youtube_url_without_www(self):
        """_detect_youtube_url should detect URL without www."""
        url = "https://youtube.com/watch?v=dQw4w9WgXcQ"
        is_youtube, video_id = _detect_youtube_url(url)
        self.assertTrue(is_youtube)
        self.assertEqual(video_id, "dQw4w9WgXcQ")

    def test_youtube_url_with_extra_params(self):
        """_detect_youtube_url should handle extra query params."""
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=42s"
        is_youtube, video_id = _detect_youtube_url(url)
        self.assertTrue(is_youtube)
        self.assertEqual(video_id, "dQw4w9WgXcQ")

    def test_youtube_url_v_not_first_param(self):
        """_detect_youtube_url should find v param not as first param."""
        url = "https://www.youtube.com/watch?list=PL12345&v=dQw4w9WgXcQ"
        is_youtube, video_id = _detect_youtube_url(url)
        self.assertTrue(is_youtube)
        self.assertEqual(video_id, "dQw4w9WgXcQ")

    def test_non_youtube_url(self):
        """_detect_youtube_url should return False for non-YouTube URL."""
        url = "https://example.com/video"
        is_youtube, video_id = _detect_youtube_url(url)
        self.assertFalse(is_youtube)
        self.assertIsNone(video_id)

    def test_youtube_url_http(self):
        """_detect_youtube_url should detect http URLs."""
        url = "http://www.youtube.com/watch?v=dQw4w9WgXcQ"
        is_youtube, video_id = _detect_youtube_url(url)
        self.assertTrue(is_youtube)
        self.assertEqual(video_id, "dQw4w9WgXcQ")

    def test_invalid_video_id_length(self):
        """_detect_youtube_url should reject video IDs not 11 chars."""
        url = "https://www.youtube.com/watch?v=short"
        is_youtube, video_id = _detect_youtube_url(url)
        self.assertFalse(is_youtube)
        self.assertIsNone(video_id)


class TestCreateUrlLink(unittest.TestCase):
    """Test suite for create_url_link function."""

    def test_creates_basic_link(self):
        """create_url_link should create basic anchor tag."""
        url = "https://example.com"
        result = create_url_link(url)
        self.assertIn('href="https://example.com"', result)
        self.assertIn('target="_blank"', result)
        self.assertIn('rel="noopener noreferrer"', result)

    def test_youtube_link_includes_embed_container(self):
        """create_url_link should add embed container for YouTube URLs."""
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        result = create_url_link(url)
        self.assertIn('class="colorblock youtube-embed-container"', result)
        self.assertIn('data-video-id="dQw4w9WgXcQ"', result)
        self.assertIn('class="youtube-player"', result)

    def test_url_with_quotes_encoded(self):
        """create_url_link should encode quotes in href."""
        url = 'https://example.com/path"test'
        result = create_url_link(url)
        self.assertIn("%22", result)


class TestCreateWikiLink(unittest.TestCase):
    """Test suite for create_wiki_link function."""

    def test_creates_wikipedia_link(self):
        """create_wiki_link should create Wikipedia link."""
        result = create_wiki_link("Test Article")
        self.assertIn('href="https://en.wikipedia.org/wiki/Test_Article"', result)
        self.assertIn('class="wikilink"', result)
        self.assertIn('target="_blank"', result)
        self.assertIn("Test Article", result)

    def test_spaces_converted_to_underscores(self):
        """create_wiki_link should convert spaces to underscores in URL."""
        result = create_wiki_link("Multiple Word Title")
        self.assertIn("Multiple_Word_Title", result)

    def test_html_in_title_stripped_for_url(self):
        """create_wiki_link should strip HTML for URL but keep for display."""
        result = create_wiki_link("<em>Emphasized</em> Title")
        self.assertIn('href="https://en.wikipedia.org/wiki/Emphasized_Title"', result)
        self.assertIn("<em>Emphasized</em> Title</a>", result)


class TestCreateEmphasis(unittest.TestCase):
    """Test suite for create_emphasis function."""

    def test_creates_em_tag(self):
        """create_emphasis should create em tag."""
        result = create_emphasis("emphasized text")
        self.assertEqual(result, "<em>emphasized text</em>")

    def test_escapes_html(self):
        """create_emphasis should escape HTML in content."""
        result = create_emphasis("<script>alert('xss')</script>")
        self.assertIn("&lt;script&gt;", result)
        self.assertNotIn("<script>", result)


class TestCreateInlineTitle(unittest.TestCase):
    """Test suite for create_inline_title function."""

    def test_creates_title_span(self):
        """create_inline_title should create span with inline-title class."""
        result = create_inline_title("Title Content")
        self.assertEqual(result, '<span class="inline-title">Title Content</span>')

    def test_preserves_html_content(self):
        """create_inline_title should preserve HTML content."""
        result = create_inline_title("<em>Styled</em> Title")
        self.assertIn("<em>Styled</em>", result)


class TestCreateTemplateHtml(unittest.TestCase):
    """Test suite for create_template_html function."""

    def test_isbn_template(self):
        """create_template_html should create ISBN span."""
        result = create_template_html("isbn", "978-0-123456-78-9")
        self.assertIn('class="isbn"', result)
        self.assertIn("978-0-123456-78-9", result)

    def test_wikidata_template(self):
        """create_template_html should create Wikidata span."""
        result = create_template_html("wikidata", "Q12345")
        self.assertIn('class="wikidata"', result)
        self.assertIn("Q12345", result)

    def test_unknown_template(self):
        """create_template_html should return sanitized content for unknown template."""
        result = create_template_html("unknown", "content")
        self.assertEqual(result, "content")

    def test_none_template_name(self):
        """create_template_html should handle None template name."""
        result = create_template_html(None, "content")
        self.assertEqual(result, "content")

    def test_escapes_html_in_content(self):
        """create_template_html should escape HTML in content."""
        result = create_template_html("isbn", "<script>bad</script>")
        self.assertIn("&lt;script&gt;", result)
        self.assertNotIn("<script>", result)


if __name__ == "__main__":
    unittest.main()
