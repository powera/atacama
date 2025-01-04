import unittest
from textwrap import dedent
from .lexer import tokenize
from .parser import parse, ParseError, NodeType, ColorNode, TextNode, Node

class TestAtacamaParser(unittest.TestCase):
    """Test suite for the Atacama parser implementation."""

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
        self.assert_node_type(ast, NodeType.DOCUMENT)
        self.assertEqual(len(ast.children), 0)

    def test_section_breaks(self):
        """Parser should handle section breaks as highest priority."""
        text = dedent("""
            First section
            ----
            Second section
            ----
            Third section
        """).strip()
        
        ast = self.parse_text(text)
        self.assert_node_type(ast, NodeType.DOCUMENT)
        self.assertEqual(len(ast.children), 3)  # Three sections
        
        for child in ast.children:
            self.assert_node_type(child, NodeType.SECTION)

    def test_multi_quote_blocks(self):
        """Parser should handle multi-paragraph quote blocks."""
        text = dedent("""
            Before quote
            <<<
            First quoted paragraph
            Second quoted paragraph
            >>>
            After quote
        """).strip()
        
        ast = self.parse_text(text)
        sections = ast.children
        self.assertEqual(len(sections), 1)
        
        section = sections[0]
        self.assertEqual(len(section.children), 3)  # Before, quote block, after
        self.assert_node_type(section.children[1], NodeType.MULTI_QUOTE)

    def test_line_color_tags(self):
        """Parser should handle line-level color tags."""
        text = "<red>Important warning"
        ast = self.parse_text(text)
        
        section = ast.children[0]
        color_node = section.children[0]
        self.assertTrue(isinstance(color_node, ColorNode))
        self.assertEqual(color_node.color, "red")
        self.assertTrue(color_node.is_line)

    def test_parenthesized_colors(self):
        """Parser should handle parenthesized color tags."""
        text = "Note: (<blue>important)"
        ast = self.parse_text(text)
        
        section = ast.children[0]
        para = section.children[0]
        
        # Text node followed by color node
        self.assertTrue(isinstance(para.children[0], TextNode))
        self.assertTrue(isinstance(para.children[1], ColorNode))
        self.assertEqual(para.children[1].color, "blue")
        self.assertFalse(para.children[1].is_line)

    def test_lists(self):
        """Parser should handle different types of lists."""
        text = dedent("""
            * Bullet item
            * Another bullet
            # Number one
            # Number two
            > Arrow item
            > Another arrow
        """).strip()
        
        ast = self.parse_text(text)
        section = ast.children[0]
        
        # Should have three lists (bullet, number, arrow)
        self.assertEqual(len(section.children), 3)
        
        for list_node in section.children:
            self.assert_node_type(list_node, NodeType.LIST)
            self.assertEqual(len(list_node.children), 2)  # Each has two items

    def test_nested_parentheses(self):
        """Parser should handle nested parentheses correctly."""
        text = "Text (outer (inner) outer)"
        ast = self.parse_text(text)
        
        section = ast.children[0]
        para = section.children[0]
        
        # Verify the structure contains nested content
        self.assertGreater(len(para.children), 1)

    def test_chinese_text(self):
        """Parser should handle Chinese text nodes."""
        text = "Hello 世界 World"
        ast = self.parse_text(text)
        
        section = ast.children[0]
        para = section.children[0]
        
        # Should have text, Chinese, text nodes
        self.assertEqual(len(para.children), 3)
        self.assert_node_type(para.children[1], NodeType.CHINESE)

    def test_special_elements(self):
        """Parser should handle URLs, wikilinks, and literal text."""
        text = dedent("""
            Visit https://example.com
            See [[Wikipedia]] article
            Code: <<print("hello")>>
        """).strip()
        
        ast = self.parse_text(text)
        section = ast.children[0]
        
        found_types = set()
        for para in section.children:
            for child in para.children:
                found_types.add(child.type)
        
        self.assertIn(NodeType.URL, found_types)
        self.assertIn(NodeType.WIKILINK, found_types)
        self.assertIn(NodeType.LITERAL, found_types)

    def test_complex_document(self):
        """Parser should handle complex documents with multiple features."""
        text = dedent("""
            Introduction
            ----
            <red>Warning:
            * First point with [[Wiki]]
            * Second with (<blue>note)
            
            <<<
            Quoted text
            More quotes
            >>>
            
            Final section with 中文
            ----
            Conclusion
        """).strip()
        
        ast = self.parse_text(text)
        self.assertGreater(len(ast.children), 1)  # Multiple sections
        
        # Test present but don't verify exact structure
        found_types = set()
        def collect_types(node):
            found_types.add(node.type)
            for child in node.children:
                collect_types(child)
                
        collect_types(ast)
        
        expected_types = {
            NodeType.SECTION, NodeType.COLOR_BLOCK, NodeType.LIST,
            NodeType.MULTI_QUOTE, NodeType.CHINESE, NodeType.WIKILINK
        }
        self.assertTrue(expected_types.issubset(found_types))

    def test_error_handling(self):
        """Parser should handle error conditions appropriately."""
        # Unmatched parentheses
        with self.assertRaises(ParseError):
            self.parse_text("Text (unclosed")
        
        # Invalid color tags
        with self.assertRaises(ParseError):
            self.parse_text("(<invalid>text)")
        
        # Unclosed multi-quote
        with self.assertRaises(ParseError):
            self.parse_text("<<< Unclosed quote")

if __name__ == '__main__':
    unittest.main()
