import unittest
from textwrap import dedent
from parser.lexer import tokenize
from parser.parser import parse, ParseError, NodeType, ColorNode, TextNode

class TestParser(unittest.TestCase):
    """Test suite for the Atacama parser component."""

    def parse_text(self, text):
        """Helper to parse text through lexer and parser."""
        tokens = tokenize(text)
        return parse(tokens)

    def assert_node_type(self, node, expected_type):
        """Helper to verify node type."""
        self.assertEqual(node.type, expected_type,
            f"Expected {expected_type.name}, got {node.type.name}")

    def test_empty_document(self):
        """Parser should handle empty input gracefully."""
        ast = self.parse_text("")
        self.assert_node_type(ast, NodeType.MESSAGE)
        self.assertEqual(len(ast.children), 0)

    def test_simple_paragraph(self):
        """Parser should create paragraph nodes for basic text."""
        ast = self.parse_text("Hello, world!")
        self.assert_node_type(ast, NodeType.MESSAGE)
        self.assertEqual(len(ast.children), 1)
        
        para = ast.children[0]
        self.assert_node_type(para, NodeType.PARAGRAPH)
        self.assertTrue(isinstance(para.children[0], TextNode))
        self.assertEqual(para.children[0].content, "Hello, world!")

    def test_color_blocks(self):
        """Parser should properly structure color blocks."""
        text = "<red>Important warning</red>"
        ast = self.parse_text(text)
        
        para = ast.children[0]
        color_node = para.children[0]
        self.assertTrue(isinstance(color_node, ColorNode))
        self.assertEqual(color_node.color, "red")
        self.assertTrue(color_node.is_block)

    def test_nested_colors(self):
        """Parser should handle nested color tags correctly."""
        text = "Note: (<red>important</red>)"
        ast = self.parse_text(text)
        
        # Verify structure: paragraph -> text -> color (inline) -> text
        para = ast.children[0]
        self.assertEqual(len(para.children), 2)  # Text and color node
        color_node = para.children[1]
        self.assertTrue(isinstance(color_node, ColorNode))
        self.assertFalse(color_node.is_block)  # Should be inline

    def test_lists(self):
        """Parser should create proper list structures."""
        text = dedent("""
            * First item
            * Second item
            # Number one
            # Number two
        """).strip()
        
        ast = self.parse_text(text)
        
        # Should have two list nodes (bullet and numbered)
        self.assertEqual(len(ast.children), 2)
        
        bullet_list = ast.children[0]
        self.assert_node_type(bullet_list, NodeType.LIST)
        self.assertEqual(len(bullet_list.children), 2)
        
        number_list = ast.children[1]
        self.assert_node_type(number_list, NodeType.LIST)
        self.assertEqual(len(number_list.children), 2)

    def test_chinese_text(self):
        """Parser should handle Chinese text nodes."""
        text = "Hello 世界 World"
        ast = self.parse_text(text)
        
        para = ast.children[0]
        self.assertEqual(len(para.children), 3)
        self.assert_node_type(para.children[1], NodeType.CHINESE)

    def test_urls_and_wikilinks(self):
        """Parser should create proper nodes for URLs and wikilinks."""
        text = "Visit https://example.com and [[Wikipedia]]"
        ast = self.parse_text(text)
        
        para = ast.children[0]
        found_url = False
        found_wiki = False
        
        for child in para.children:
            if child.type == NodeType.URL:
                found_url = True
            elif child.type == NodeType.WIKILINK:
                found_wiki = True
        
        self.assertTrue(found_url, "URL node not found")
        self.assertTrue(found_wiki, "Wikilink node not found")

    def test_section_breaks(self):
        """Parser should handle section breaks."""
        text = "Section 1\n----\nSection 2"
        ast = self.parse_text(text)
        
        self.assertEqual(len(ast.children), 3)
        self.assert_node_type(ast.children[1], NodeType.BREAK)

    def test_complex_nesting(self):
        """Parser should handle complex nested structures."""
        text = dedent("""
            <red>Important:
            * First point with [[Wiki]]
            * Second point with (<blue>note</blue>)
            </red>
        """).strip()
        
        ast = self.parse_text(text)
        # Verify basic structure without checking every detail
        self.assertTrue(len(ast.children) > 0)
        color_node = ast.children[0].children[0]
        self.assertTrue(isinstance(color_node, ColorNode))
        self.assertEqual(color_node.color, "red")

    def test_error_recovery(self):
        """Parser should recover from or report errors appropriately."""
        # Missing closing tag
        with self.assertRaises(ParseError):
            self.parse_text("<red>Unclosed")
        
        # Mismatched tags
        with self.assertRaises(ParseError):
            self.parse_text("<red>Wrong</blue>")
        
        # Invalid nesting
        with self.assertRaises(ParseError):
            self.parse_text("<red><blue>Wrong order</red></blue>")

if __name__ == '__main__':
    unittest.main()
