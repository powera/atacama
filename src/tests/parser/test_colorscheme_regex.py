import unittest
from parser.colorscheme import ColorScheme

class TestColorPatterns(unittest.TestCase):
    """Test color pattern regex matching."""
    
    def setUp(self):
        """Create ColorScheme instance for tests."""
        self.processor = ColorScheme()

    def test_basic_color_pattern(self):
        """Test basic color pattern matches."""
        test_cases = [
            ("<red>text", [("red", "text", None, None)]),
            ("<blue>nested text", [("blue", "nested text", None, None)]),
            ("regular text", []),
            ("<invalid>text", [])  # Should not match invalid color
        ]
        
        for text, expected in test_cases:
            sanitized = self.processor.sanitize_html(text)
            matches = list(self.processor.color_pattern.finditer(sanitized))
            self.assertEqual(len(matches), len(expected))
            for match, (e_color, e_text, e_nested_color, e_nested_text) in zip(matches, expected):
                self.assertEqual(match.groups(), (e_color, e_text, e_nested_color, e_nested_text))

    def test_nested_color_pattern(self):
        """Test nested color pattern matches in parentheses."""
        test_cases = [
            ("(<red>text)", [(None, None, "red", "text")]),
            ("text (<blue>nested)", [(None, None, "blue", "nested")]),
            ("(<invalid>text)", [])  # Should not match invalid color
        ]
        
        for text, expected in test_cases:
            sanitized = self.processor.sanitize_html(text)
            matches = list(self.processor.color_pattern.finditer(sanitized))
            self.assertEqual(len(matches), len(expected))
            for match, (e_color, e_text, e_nested_color, e_nested_text) in zip(matches, expected):
                self.assertEqual(match.groups(), (e_color, e_text, e_nested_color, e_nested_text))

    def test_multiple_color_patterns(self):
        """Test multiple color patterns in same text."""
        text = "<red>first\n(<blue>second)"
        sanitized = self.processor.sanitize_html(text)
        matches = list(self.processor.color_pattern.finditer(sanitized))
        self.assertEqual(len(matches), 2)
        self.assertEqual(matches[0].groups(), ("red", "first", None, None))
        self.assertEqual(matches[1].groups(), (None, None, "blue", "second"))

    def test_complex_nested_colors(self):
        """Test multiple nested color patterns in a single line."""
        text = "<red> The color is (<blue> blue) and (<green> green)."
        sanitized = self.processor.sanitize_html(text)
        matches = list(self.processor.color_pattern.finditer(sanitized))
        self.assertEqual(len(matches), 3)
        self.assertEqual(matches[0].groups(), ("red", " The color is (<blue> blue) and (<green> green).", None, None))
        self.assertEqual(matches[1].groups(), (None, None, "blue", " blue"))
        self.assertEqual(matches[2].groups(), (None, None, "green", " green"))

    def test_inline_color_pattern(self):
        """Test inline color pattern matches."""
        test_cases = [
            ("<red>inline text", [("red", "inline text")]),
            ("text <blue>more text", [("blue", "more text")]),
            ("<invalid>text", [])  # Should not match invalid color
        ]
        
        for text, expected in test_cases:
            sanitized = self.processor.sanitize_html(text)
            matches = list(self.processor.inline_color_pattern.finditer(sanitized))
            self.assertEqual(len(matches), len(expected))
            for match, (e_color, e_text) in zip(matches, expected):
                self.assertEqual(match.groups(), (e_color, e_text))

class TestChinesePattern(unittest.TestCase):
    """Test Chinese character pattern matching."""
    
    def setUp(self):
        self.processor = ColorScheme()

    def test_chinese_matches(self):
        """Test Chinese character pattern matches."""
        test_cases = [
            ("你好", ["你好"]),
            ("Hello 世界", ["世界"]),
            ("No Chinese", []),
            ("混合Chinese文字", ["混合", "文字"])
        ]
        
        for text, expected in test_cases:
            sanitized = self.processor.sanitize_html(text)
            matches = list(self.processor.chinese_pattern.finditer(sanitized))
            self.assertEqual([m.group(0) for m in matches], expected)

class TestMultilineBlockPattern(unittest.TestCase):
    """Test multiline block pattern matching."""
    
    def setUp(self):
        self.processor = ColorScheme()

    def test_basic_blocks(self):
        """Test basic multiline block matches."""
        test_cases = [
            ("<<<simple block>>>", [("simple block", None)]),
            ("<<<multi\nline\nblock>>>", [("multi\nline\nblock", None)]),
            ("<<<block\n----\n", [("block", "\n----\n")]),
            ("not a block", [])
        ]
        
        for text, expected in test_cases:
            sanitized = self.processor.sanitize_html(text)
            matches = list(self.processor.multiline_block_pattern.finditer(sanitized))
            self.assertEqual(len(matches), len(expected))
            for match, (e_content, e_break) in zip(matches, expected):
                self.assertEqual(match.groups(), (e_content, e_break))

class TestListPattern(unittest.TestCase):
    """Test list pattern matching."""
    
    def setUp(self):
        self.processor = ColorScheme()

    def test_list_matches(self):
        """Test list marker pattern matches."""
        test_cases = [
            ("* bullet point", [("*", "bullet point")]),
            ("# numbered item", [("#", "numbered item")]),
            ("> arrow item", [("&gt;", "arrow item")]),
            ("not a list", [])
        ]
        
        for text, expected in test_cases:
            sanitized = self.processor.sanitize_html(text)
            matches = list(self.processor.list_pattern.finditer(sanitized))
            self.assertEqual(len(matches), len(expected))
            for match, (e_marker, e_content) in zip(matches, expected):
                self.assertEqual(match.groups(), (e_marker, e_content))

    def test_indented_lists(self):
        """Test indented list pattern matches."""
        test_cases = [
            ("  * indented bullet", [("*", "indented bullet")]),
            ("\t# tabbed number", [("#", "tabbed number")]),
            ("    > deeply indented", [("&gt;", "deeply indented")])
        ]
        
        for text, expected in test_cases:
            sanitized = self.processor.sanitize_html(text)
            matches = list(self.processor.list_pattern.finditer(sanitized))
            self.assertEqual(len(matches), len(expected))
            for match, (e_marker, e_content) in zip(matches, expected):
                self.assertEqual(match.groups(), (e_marker, e_content))

class TestEmphasisPattern(unittest.TestCase):
    """Test emphasis pattern matching."""
    
    def setUp(self):
        self.processor = ColorScheme()

    def test_emphasis_matches(self):
        """Test emphasis pattern matches."""
        test_cases = [
            ("*emphasized*", ["emphasized"]),
            ("text with *emphasis* in it", ["emphasis"]),
            ("**not matched**", []),  # Double asterisks not matched
            ("no emphasis", []),
            ("multiple *words* in *text*", ["words", "text"])
        ]
        
        for text, expected in test_cases:
            sanitized = self.processor.sanitize_html(text)
            matches = list(self.processor.emphasis_pattern.finditer(sanitized))
            self.assertEqual([m.group(1) for m in matches], expected)

class TestUrlPattern(unittest.TestCase):
    """Test URL pattern matching."""
    
    def setUp(self):
        self.processor = ColorScheme()

    def test_url_matches(self):
        """Test URL pattern matches."""
        test_cases = [
            ("https://example.com", ["https://example.com"]),
            ("http://sub.domain.com/path", ["http://sub.domain.com/path"]),
            ("Visit https://site.com/page?param=1", ["https://site.com/page?param=1"]),
            ("no url here", []),
            ("multiple https://one.com and http://two.com", 
             ["https://one.com", "http://two.com"])
        ]
        
        for text, expected in test_cases:
            sanitized = self.processor.sanitize_html(text)
            matches = list(self.processor.url_pattern.finditer(sanitized))
            self.assertEqual([m.group(0) for m in matches], expected)

class TestWikilinkPattern(unittest.TestCase):
    """Test wikilink pattern matching."""
    
    def setUp(self):
        self.processor = ColorScheme()

    def test_wikilink_matches(self):
        """Test wikilink pattern matches."""
        test_cases = [
            ("[[Simple]]", ["Simple"]),
            ("[[Multi Word]]", ["Multi Word"]),
            ("[[Link 1]] and [[Link 2]]", ["Link 1", "Link 2"]),
            ("no wikilink", []),
            ("incomplete [[", [])
        ]
        
        for text, expected in test_cases:
            sanitized = self.processor.sanitize_html(text)
            matches = list(self.processor.wikilink_pattern.finditer(sanitized))
            self.assertEqual([m.group(1) for m in matches], expected)

if __name__ == '__main__':
    unittest.main()
