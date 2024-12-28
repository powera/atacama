import unittest
from textwrap import dedent
from parser.lexer import tokenize
from parser.parser import parse
from parser.html_generator import generate_html, HTMLGenerator

class TestHTMLGenerator(unittest.TestCase):
    """Test suite for the Atacama HTML generator component."""

    def generate_html(self, text, annotations=None):
        """Helper to process text through the full pipeline."""
        tokens = tokenize(text)
        ast = parse(tokens)
        return generate_html(ast, annotations)

    def assertHtmlEqual(self, actual, expected):
        """Compare HTML strings ignoring whitespace differences."""
        def normalize(html):
            return ' '.join(html.split())
        self.assertEqual(normalize(actual), normalize(expected))

    def test_basic_text(self):
        """Basic text should be wrapped in paragraph tags."""
        html = self.generate_html("Hello, world!")
        self.assertHtmlEqual(html, "<p>Hello, world!</p>")

        # Multiple paragraphs should be separated
        html = self.generate_html("Para 1\n\nPara 2")
        self.assertHtmlEqual(html, "<p>Para 1</p> <p>Para 2</p>")

    def test_color_blocks(self):
        """Color blocks should include proper classes and emoji indicators."""
        text = "<red>Important warning</red>"
        html = self.generate_html(text)
        expected = '''
            <p class="color-red">
                <span class="sigil" title="Forceful/certain">💡</span>
                <div class="color-content">Important warning</div>
            </p>
        '''
        self.assertHtmlEqual(html, expected)

        # Test nested color blocks
        text = "<red>Outer <blue>inner</blue> text</red>"
        html = self.generate_html(text)
        self.assertIn('class="color-red"', html)
        self.assertIn('class="color-blue"', html)
        self.assertIn('💡', html)  # Red's emoji
        self.assertIn('✨', html)  # Blue's emoji

    def test_inline_colors(self):
        """Inline colored text should preserve parentheses and proper nesting."""
        text = "Note: (<red>important</red>)"
        html = self.generate_html(text)
        self.assertIn('<p>Note: <span class="color-red">', html)
        self.assertIn('</span></p>', html)
        self.assertIn('💡', html)  # Red's emoji
        self.assertIn('(', html)
        self.assertIn(')', html)

    def test_lists(self):
        """Lists should have proper structure and classes."""
        text = dedent("""
            * First item
            * Second item with (<red>note</red>)
            # Numbered item
            > Arrow item
        """).strip()
        
        html = self.generate_html(text)
        
        # Check list containers
        self.assertIn('<ul>', html)
        self.assertIn('</ul>', html)
        
        # Check list item classes
        self.assertIn('class="bullet-list"', html)
        self.assertIn('class="number-list"', html)
        self.assertIn('class="arrow-list"', html)
        
        # Check nested color in list item
        self.assertIn('class="color-red"', html)

    def test_chinese_text(self):
        """Chinese text should include proper annotation attributes."""
        text = "Hello 世界 World"
        annotations = {
            "世界": {
                "pinyin": "Shì Jiè",
                "definition": "world"
            }
        }
        
        html = self.generate_html(text, annotations)
        
        self.assertIn('class="annotated-chinese"', html)
        self.assertIn('data-pinyin="Shì Jiè"', html)
        self.assertIn('data-definition="world"', html)
        
        # Test without annotations
        html = self.generate_html(text)
        self.assertIn('class="annotated-chinese"', html)
        self.assertIn('世界', html)

    def test_urls_and_wikilinks(self):
        """URLs and wikilinks should have proper attributes."""
        text = "Visit https://example.com and [[Wikipedia]]"
        html = self.generate_html(text)
        
        # Check URL
        self.assertIn('<a href="https://example.com"', html)
        self.assertIn('target="_blank"', html)
        self.assertIn('rel="noopener noreferrer"', html)
        
        # Check wikilink
        self.assertIn('<a href="https://en.wikipedia.org/wiki/Wikipedia"', html)
        self.assertIn('class="wikilink"', html)

    def test_section_breaks(self):
        """Section breaks should be converted to HR elements."""
        text = "Section 1\n----\nSection 2"
        html = self.generate_html(text)
        self.assertIn('<hr>', html)
        self.assertIn('<p>Section 1</p>', html)
        self.assertIn('<p>Section 2</p>', html)

    def test_literal_text(self):
        """Literal text should be properly wrapped."""
        text = "Code: <<print('hello')>>"
        html = self.generate_html(text)
        self.assertIn('<span class="literal-text">', html)
        self.assertIn("print('hello')", html)

    def test_complex_document(self):
        """Test a complex document with multiple features."""
        text = dedent("""
            Welcome to my 笔记

            <red>Important points:</red>
            * First item with [[Wiki]]
            * Second item with 中文
            * Third with (<blue>note</blue>)

            Visit https://example.com for more.
            ----
            That's all!
        """).strip()

        annotations = {
            "笔记": {"pinyin": "Bǐ Jì", "definition": "notes"},
            "中文": {"pinyin": "Zhōng Wén", "definition": "Chinese language"}
        }

        html = self.generate_html(text, annotations)

        # Verify essential structure elements
        self.assertIn('class="annotated-chinese"', html)
        self.assertIn('class="color-red"', html)
        self.assertIn('class="color-blue"', html)
        self.assertIn('class="bullet-list"', html)
        self.assertIn('class="wikilink"', html)
        self.assertIn('<hr>', html)
        self.assertIn('href="https://example.com"', html)

    def test_empty_and_whitespace(self):
        """Test handling of empty or whitespace-only input."""
        self.assertEqual(self.generate_html("").strip(), "")
        self.assertEqual(self.generate_html(" \n \t ").strip(), "")
        self.assertEqual(self.generate_html("\n\n\n").strip(), "")

    def test_malformed_html_escaping(self):
        """Test that potentially malicious HTML is escaped."""
        text = 'Text with <script>alert("xss")</script>'
        html = self.generate_html(text)
        self.assertNotIn('<script>', html)
        self.assertIn('&lt;script&gt;', html)

if __name__ == '__main__':
    unittest.main()
