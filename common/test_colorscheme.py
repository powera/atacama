import unittest
from common.colorscheme import ColorScheme

class TestLists(unittest.TestCase):
    """Test list processing functionality."""
    
    def setUp(self):
        """Create ColorScheme instance for tests."""
        self.processor = ColorScheme()

    def test_bullet_list(self):
        """Test processing of bullet lists."""
        content = "* First item\n* Second item"
        processed = self.processor.process_content(content)
        self.assertIn('<li class="bullet-list">First item</li>', processed)
        self.assertIn('<li class="bullet-list">Second item</li>', processed)
        self.assertIn('<ul>', processed)
        self.assertIn('</ul>', processed)

    def test_numbered_list(self):
        """Test processing of numbered lists."""
        content = "# First item\n# Second item"
        processed = self.processor.process_content(content)
        self.assertIn('<li class="number-list">First item</li>', processed)
        self.assertIn('<li class="number-list">Second item</li>', processed)

    def test_arrow_list(self):
        """Test processing of arrow lists."""
        content = "> First item\n> Second item"
        processed = self.processor.process_content(content)
        self.assertIn('<li class="arrow-list">First item</li>', processed)
        self.assertIn('<li class="arrow-list">Second item</li>', processed)

    def test_mixed_lists(self):
        """Test processing of mixed list types."""
        content = "* Bullet item\n# Number item\n> Arrow item"
        processed = self.processor.process_content(content)
        self.assertIn('<li class="bullet-list">Bullet item</li>', processed)
        self.assertIn('<li class="number-list">Number item</li>', processed)
        self.assertIn('<li class="arrow-list">Arrow item</li>', processed)

class TestHtmlSanitization(unittest.TestCase):
    """Test HTML sanitization and preservation."""
    
    def setUp(self):
        self.processor = ColorScheme()

    def test_preserve_color_tags(self):
        """Test that color tags are properly preserved."""
        content = "<red>Important text</red>"
        processed = self.processor.process_content(content)
        self.assertIn('class="color-red"', processed)
        self.assertIn('>Important text</span>', processed)
        self.assertNotIn('__PRESERVED', processed)

    def test_preserve_nested_tags(self):
        """Test preservation of nested color tags."""
        content = "<red>Alert: <blue>Critical update</blue> required</red>"
        processed = self.processor.process_content(content)
        self.assertIn('class="color-red"', processed)
        self.assertIn('class="color-blue"', processed)
        self.assertIn('Critical update', processed)
        self.assertNotIn('__PRESERVED', processed)

    def test_escape_malicious_html(self):
        """Test that potentially malicious HTML is escaped."""
        content = '<script>alert("xss")</script>'
        processed = self.processor.process_content(content)
        self.assertNotIn('<script>', processed)
        self.assertIn('&lt;script&gt;', processed)

class TestChineseProcessing(unittest.TestCase):
    """Test Chinese character processing."""
    
    def setUp(self):
        self.processor = ColorScheme()

    def test_basic_chinese_wrapping(self):
        """Test that Chinese characters are wrapped in spans."""
        content = "Hello 你好 World"
        processed = self.processor.process_content(content)
        self.assertIn('<span class="annotated-chinese">你好</span>', processed)

    def test_chinese_with_annotations(self):
        """Test Chinese characters with annotations."""
        content = "The word 你好 means hello"
        annotations = {
            "你好": {
                "pinyin": "ni3 hao3",
                "definition": "hello"
            }
        }
        processed = self.processor.process_content(content, chinese_annotations=annotations)
        self.assertIn('data-pinyin="ni3 hao3"', processed)
        self.assertIn('data-definition="hello"', processed)

    def test_chinese_without_annotations(self):
        """Test Chinese characters without annotations."""
        content = "Some chinese: 测试"
        processed = self.processor.process_content(content)
        self.assertIn('<span class="annotated-chinese">测试</span>', processed)

    def test_chinese_with_html_escaping(self):
        """Test Chinese annotations with characters needing HTML escaping."""
        content = "Test 测试"
        annotations = {
            "测试": {
                "pinyin": 'ce"shi',  # Contains quotes
                "definition": 'test & verify'  # Contains ampersand
            }
        }
        processed = self.processor.process_content(content, chinese_annotations=annotations)
        self.assertIn('&quot;', processed)  # Quotes should be escaped
        self.assertIn('&amp;', processed)   # Ampersand should be escaped

class TestColorProcessing(unittest.TestCase):
    """Test color tag processing."""

    def setUp(self):
        self.processor = ColorScheme()

    def test_paragraph_color(self):
        """Test paragraph-level color processing."""
        content = "<blue>A mystical message"
        processed = self.processor.process_content(content)
        self.assertIn('class="color-blue"', processed)
        self.assertIn('<span class="sigil">✨</span>', processed)

    def test_nested_colors_in_parentheses(self):
        """Test nested color processing within parentheses."""
        content = "A note (<red>important)"
        processed = self.processor.process_content(content)
        self.assertIn('class="color-red"', processed)
        self.assertIn('<span class="sigil">💡</span>', processed)
        self.assertIn('(', processed)  # Check parentheses preserved

class TestParagraphProcessing(unittest.TestCase):
    """Test paragraph and line break processing."""

    def setUp(self):
        self.processor = ColorScheme()

    def test_basic_paragraphs(self):
        """Test basic paragraph processing."""
        content = "First paragraph\n\nSecond paragraph"
        processed = self.processor.process_content(content)
        self.assertIn('<p>First paragraph</p>', processed)
        self.assertIn('<p>Second paragraph</p>', processed)

    def test_line_breaks(self):
        """Test line break processing within paragraphs."""
        content = "Line one\nLine two"
        processed = self.processor.process_content(content)
        self.assertIn('<br>', processed)

    def test_section_breaks(self):
        """Test section break processing."""
        content = "Section 1\n----\nSection 2"
        processed = self.processor.process_content(content)
        self.assertIn('<hr>', processed)

class TestUrlAndWikilinkProcessing(unittest.TestCase):
    """Test URL and wikilink processing."""

    def setUp(self):
        self.processor = ColorScheme()

    def test_url_processing(self):
        """Test URL conversion to links."""
        content = "Visit https://example.com"
        processed = self.processor.process_content(content)
        self.assertIn('<a href="https://example.com"', processed)
        self.assertIn('target="_blank"', processed)
        self.assertIn('rel="noopener noreferrer"', processed)

    def test_wikilink_processing(self):
        """Test wikilink conversion."""
        content = "See [[Python]]"
        processed = self.processor.process_content(content)
        self.assertIn('<a href="https://en.wikipedia.org/wiki/Python"', processed)
        self.assertIn('class="wikilink"', processed)

if __name__ == '__main__':
    unittest.main()
