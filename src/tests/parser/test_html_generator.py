import unittest
from textwrap import dedent
from parser.lexer import tokenize
from parser.parser import parse
from parser.html_generator import generate_html, HTMLGenerator

class TestAtacamaHTMLGenerator(unittest.TestCase):
    """Test suite for the Atacama HTML generator implementation."""

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

    def test_document_structure(self):
        """Test basic document structure with sections."""
        text = dedent("""
            First section
            ----
            Second section
            ----
            Third section
        """).strip()
        
        html = self.generate_html(text)
        self.assertHtmlEqual(html, """
            <section class="content-section">
                <p>First section</p>
            </section>
            <section class="content-section">
                <p>Second section</p>
            </section>
            <section class="content-section">
                <p>Third section</p>
            </section>
        """)

    def test_multi_quote_blocks(self):
        """Test multi-paragraph quote block formatting."""
        text = dedent("""
            Before quote
            <<<
            First quoted paragraph
            Second quoted paragraph
            >>>
            After quote
        """).strip()
        
        html = self.generate_html(text)
        self.assertHtmlEqual(html, """
            <section class="content-section">
                <p>Before quote</p>
                <blockquote class="multi-quote">
                    <p>First quoted paragraph</p>
                    <p>Second quoted paragraph</p>
                </blockquote>
                <p>After quote</p>
            </section>
        """)

    def test_line_color_tags(self):
        """Test line-level color tag formatting."""
        text = "<red>Important warning"
        html = self.generate_html(text)
        
        self.assertHtmlEqual(html, """
            <section class="content-section">
                <div class="color-red color-line">
                    <span class="sigil" title="Forceful/certain">💡</span>
                    <span class="colortext-content">Important warning</span>
                </div>
            </section>
        """)

    def test_parenthesized_colors(self):
        """Test parenthesized color tag formatting."""
        text = "Note: (<red>important)"
        html = self.generate_html(text)
        
        self.assertHtmlEqual(html, """
            <section class="content-section">
                <p>Note: <span class="color-red color-paren">
                    <span class="sigil" title="Forceful/certain">💡</span>
                    <span class="colortext-content">(important)</span>
                </span></p>
            </section>
        """)

    def test_lists(self):
        """Test list formatting with different marker types."""
        text = dedent("""
            * First item
            * Second item
            # Number item
            > Arrow item
        """).strip()
        
        html = self.generate_html(text)
        
        self.assertIn('<ul class="atacama-list">', html)
        self.assertIn('<li class="bullet-list">', html)
        self.assertIn('<li class="number-list">', html)
        self.assertIn('<li class="arrow-list">', html)

    def test_chinese_text(self):
        """Test Chinese text with annotations."""
        text = "Hello 世界 World"
        annotations = {
            "世界": {
                "pinyin": "Shì Jiè",
                "definition": "world"
            }
        }
        
        html = self.generate_html(text, annotations)
        self.assertHtmlEqual(html, """
            <section class="content-section">
                <p>Hello <span class="annotated-chinese" 
                    data-pinyin="Shì Jiè" 
                    data-definition="world">世界</span> World</p>
            </section>
        """)

    def test_special_elements(self):
        """Test URLs, wikilinks, and literal text elements."""
        text = dedent("""
            Visit https://example.com
            Read [[Wikipedia]] article
            Code: <<print("hello")>>
        """).strip()
        
        html = self.generate_html(text)
        
        self.assertIn('class="external-link"', html)
        self.assertIn('rel="noopener noreferrer"', html)
        self.assertIn('class="wikilink"', html)
        self.assertIn('class="literal-text"', html)

    def test_nested_structures(self):
        """Test complex nested structures."""
        text = dedent("""
            <red>Warning:
            * Item with (<blue>note)
            * Item with <<code>>
            >>>
        """).strip()
        
        html = self.generate_html(text)
        
        self.assertIn('class="color-red color-line"', html)
        self.assertIn('class="color-blue color-paren"', html)
        self.assertIn('class="atacama-list"', html)
        self.assertIn('class="bullet-list"', html)
        self.assertIn('class="literal-text"', html)

    def test_html_escaping(self):
        """Test proper HTML escaping."""
        cases = [
            ('Text & more', '&amp;'),
            ('Text < text', '&lt;'),
            ('Text > text', '&gt;'),
            ('Text "quoted"', '"quoted"'),  # Quotes don't need escaping in content
            ('<script>alert("xss")</script>', '&lt;script&gt;')
        ]
        
        for input_text, expected in cases:
            html = self.generate_html(input_text)
            self.assertIn(expected, html)

    def test_url_sanitization(self):
        """Test URL sanitization in links."""
        text = 'Visit https://example.com/"malicious'
        html = self.generate_html(text)
        self.assertIn('href="https://example.com/%22malicious"', html)
        self.assertNotIn('href="https://example.com/"malicious"', html)

    def test_complex_document(self):
        """Test a complete document with multiple features."""
        text = dedent("""
            Welcome
            ----
            <red>Important:
            * Point with [[Wiki]]
            * Point with 中文
            
            <<<
            Quoted content
            More quotes
            >>>
            
            Visit https://example.com
        """).strip()
        
        html = self.generate_html(text)
        
        # Verify document structure
        self.assertIn('<section class="content-section">', html)
        self.assertIn('<blockquote class="multi-quote">', html)
        
        # Verify formatting elements
        self.assertIn('class="color-red color-line"', html)
        self.assertIn('class="wikilink"', html)
        self.assertIn('class="annotated-chinese"', html)
        self.assertIn('class="external-link"', html)

if __name__ == '__main__':
    unittest.main()
