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
            <hr class="section-break" />
            <section class="content-section">
                <p>Second section</p>
            </section>
            <hr class="section-break" />
            <section class="content-section">
                <p>Third section</p>
            </section>
        """)

    def test_empty_document(self):
        """Test handling of empty document."""
        html = self.generate_html("")
        self.assertEqual(html, "")

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
                <div class="mlq">
                    <button type="button" class="mlq-collapse" aria-label="Toggle visibility">
                        <span class="mlq-collapse-icon">−</span>
                    </button>
                    <div class="mlq-content">
                        <p>First quoted paragraph</p>
                        <p>Second quoted paragraph</p>
                    </div>
                </div>
                <p>After quote</p>
            </section>
        """)

    def test_nested_multi_quote(self):
        """Test handling of nested multi-quote blocks."""
        text = dedent("""
            <<<
            Outer quote
            <<<
            Inner quote
            >>>
            Still outer
            >>>
        """).strip()
        
        html = self.generate_html(text)
        self.assertIn('class="mlq"', html)
        self.assertIn('class="mlq-content"', html)
        self.assertIn('Outer quote', html)
        self.assertIn('Inner quote', html)
        self.assertIn('Still outer', html)

    def test_line_color_tags(self):
        """Test line-level color tag formatting."""
        text = "<red>Important warning"
        html = self.generate_html(text)
        
        self.assertHtmlEqual(html, """
            <section class="content-section">
                <p><span class="colorblock color-red">
                    <span class="sigil">💡</span>
                    <span class="colortext-content">Important warning</span>
                </span></p>
            </section>
        """)

    def test_nested_color_tags(self):
        """Test nested color tag formatting."""
        text = "<red>Warning: (<blue>critical) alert"
        html = self.generate_html(text)
        self.assertIn('class="colorblock color-red"', html)
        self.assertIn('class="colorblock color-blue"', html)
        self.assertIn('<span class="sigil">💡</span>', html)
        self.assertIn('<span class="sigil">✨</span>', html)

    def test_lists(self):
        """Test list formatting with different marker types."""
        text = dedent("""
            * First item
            * Second item
            # Number item
            > Arrow item
        """).strip()
        
        html = self.generate_html(text)
        self.assertIn('<ul>', html)
        self.assertIn('<li class="bullet-list">', html)
        self.assertIn('<li class="number-list">', html)
        self.assertIn('<li class="arrow-list">', html)

    def test_nested_lists(self):
        """Test nested list structures."""
        text = dedent("""
            * Parent item
            * Parent with nested
            # Nested number
            > Nested arrow
            * Back to parent
        """).strip()
        
        html = self.generate_html(text)
        self.assertIn('<ul>', html)
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

    def test_chinese_without_annotation(self):
        """Test Chinese text without annotations."""
        text = "Hello 世界 World"
        html = self.generate_html(text)
        self.assertIn('<span class="annotated-chinese"', html)
        self.assertNotIn('data-pinyin', html)
        self.assertNotIn('data-definition', html)
        self.assertIn('世界</span>', html)

    def test_url_formatting(self):
        """Test URL formatting and attributes."""
        text = "Visit https://example.com/page"
        html = self.generate_html(text)
        self.assertIn('href="https://example.com/page"', html)
        self.assertIn('rel="noopener noreferrer"', html)
        self.assertIn('target="_blank"', html)

    def test_wikilinks(self):
        """Test wiki-style links."""
        text = "See [[Article Name]] for details"
        html = self.generate_html(text)
        self.assertIn('class="wikilink"', html)
        self.assertIn('href="https://en.wikipedia.org/wiki/Article_Name"', html)
        self.assertIn('target="_blank"', html)
        self.assertIn('Article Name', html)

    def test_literal_text(self):
        """Test literal text blocks."""
        text = "Code: <<print('hello')>>"
        html = self.generate_html(text)
        self.assertIn('class="literal-text"', html)
        self.assertIn("print('hello')", html)

    def test_emphasis(self):
        """Test emphasized text."""
        text = "This is *emphasized* text"
        html = self.generate_html(text)
        self.assertIn('<em>', html)
        self.assertIn('emphasized', html)
        self.assertIn('</em>', html)

    def test_templates(self):
        """Test template formatting."""
        cases = [
            ('{{pgn|rnbqkbnr/pp1ppppp/8/2p5/4P3/5N2/PPPP1PPP/RNBQKB1R b KQkq - 1 2}}', 'chess-board'),
            ('{{isbn|1234567890}}', 'isbn'),
            ('{{wikidata|Q12345}}', 'wikidata')
        ]
        
        for input_text, expected_class in cases:
            html = self.generate_html(input_text)
            self.assertIn(f'class="{expected_class}"', html)

    def test_html_escaping(self):
        """Test proper HTML escaping."""
        cases = [
            ('Text & more', '&amp;'),
            ('Text < text', '&lt;'),
            ('Text > text', '&gt;'),
            ('Text "quoted"', '"quoted"'),
            ('<script>alert("xss")</script>', '&lt;script&gt;')
        ]
        
        for input_text, expected in cases:
            html = self.generate_html(input_text)
            self.assertIn(expected, html)

    def test_complex_document(self):
        """Test a complete document with multiple features."""
        text = dedent("""
            Welcome to our guide
            ----
            <red>Important notice:
            * Key point with [[Reference]]
            * Another point with 中文
            
            <<<
            This is a quoted section
            With multiple paragraphs
            >>>
            
            Check https://example.com for *more* details
            
            {{isbn|1234567890}}
        """).strip()
        
        html = self.generate_html(text)
        
        # Verify structural elements
        self.assertIn('<section class="content-section">', html)
        self.assertIn('<hr class="section-break"', html)
        self.assertIn('class="mlq"', html)
        
        # Verify color formatting
        self.assertIn('class="colorblock color-red"', html)
        self.assertIn('<span class="sigil">💡</span>', html)
        
        # Verify other elements
        self.assertIn('class="wikilink"', html)
        self.assertIn('class="annotated-chinese"', html)
        self.assertIn('target="_blank"', html)
        self.assertIn('class="isbn"', html)
        self.assertIn('<em>', html)

if __name__ == '__main__':
    unittest.main()
