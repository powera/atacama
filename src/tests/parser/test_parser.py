import unittest
from textwrap import dedent
from parser.lexer import tokenize, TokenType
from parser.parser import parse, NodeType, ColorNode, Node, ListItemNode

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

    def test_basic_text(self):
        """Parser should handle basic text correctly."""
        text = "Hello, world!"
        ast = self.parse_text(text)
        self.assert_node_type(ast, NodeType.DOCUMENT)
        self.assertEqual(len(ast.children), 1)
        self.assert_node_type(ast.children[0], NodeType.TEXT)
        self.assertEqual(ast.children[0].token.value, "Hello, world!")

    def test_horizontal_rules(self):
        """Parser should handle horizontal rules (section breaks)."""
        text = dedent("""
            First part
            ----
            Second part
        """).strip()
        
        ast = self.parse_text(text)
        self.assert_node_type(ast, NodeType.DOCUMENT)
        
        # Should have text, HR, text nodes
        self.assertEqual(len(ast.children), 5)  # text, newline, HR, newline, text
        self.assert_node_type(ast.children[2], NodeType.HR)

    def test_multi_quote_blocks(self):
        """Parser should handle multi-line quote blocks (MLQ)."""
        text = dedent("""
            Before quote
            <<<
            First quoted line
            Second quoted line
            >>>
            After quote
        """).strip()
        
        ast = self.parse_text(text)
        self.assert_node_type(ast, NodeType.DOCUMENT)
        
        # Find MLQ node
        mlq_nodes = [n for n in ast.children if n.type == NodeType.MLQ]
        self.assertEqual(len(mlq_nodes), 1)
        
        # Verify MLQ content
        mlq = mlq_nodes[0]
        text_children = [n for n in mlq.children if n.type == NodeType.TEXT]
        self.assertGreater(len(text_children), 0)

    def test_colored_multi_quote_blocks(self):
        """Parser should handle colored multi-line quote blocks."""
        text = dedent("""
            Before quote
            <red> <<<
            First quoted line
            Second quoted line
            >>>
            After quote
        """).strip()
        
        ast = self.parse_text(text)
        self.assert_node_type(ast, NodeType.DOCUMENT)
        
        # Check for ColorNode that contains an MLQ
        color_nodes = [n for n in ast.children if isinstance(n, ColorNode)]
        self.assertEqual(len(color_nodes), 1)
        
        # Verify color node attributes
        color_node = color_nodes[0]
        self.assertEqual(color_node.color, "red")
        self.assertTrue(color_node.is_line)
        
        # Verify it contains an MLQ node
        self.assertEqual(len(color_node.children), 1)
        self.assert_node_type(color_node.children[0], NodeType.MLQ)
        
        # Verify MLQ content
        mlq = color_node.children[0]
        text_children = [n for n in mlq.children if n.type == NodeType.TEXT]
        self.assertGreater(len(text_children), 0)

    def test_unclosed_mlq(self):
        """Parser should handle unclosed MLQ blocks gracefully."""
        text = dedent("""
            Start
            <<<
            Unclosed block
        """).strip()
        
        ast = self.parse_text(text)
        # Should convert unclosed MLQ to text
        self.assertTrue(any(n.type == NodeType.TEXT and '<<<' in n.token.value 
                          for n in ast.children))

    def test_line_color_tags(self):
        """Parser should handle line-level color tags."""
        text = "<red>Important warning"
        ast = self.parse_text(text)
        
        color_nodes = [n for n in ast.children if isinstance(n, ColorNode)]
        self.assertEqual(len(color_nodes), 1)
        self.assertEqual(color_nodes[0].color, "red")
        self.assertTrue(color_nodes[0].is_line)

    def test_parenthesized_colors(self):
        """Parser should handle parenthesized color tags."""
        text = "Note: (<blue>important)"
        ast = self.parse_text(text)
        
        # Should have text and color nodes
        self.assertGreaterEqual(len(ast.children), 2)
        color_nodes = [n for n in ast.children if isinstance(n, ColorNode)]
        self.assertEqual(len(color_nodes), 1)
        self.assertEqual(color_nodes[0].color, "blue")
        self.assertFalse(color_nodes[0].is_line)

    def test_unclosed_color(self):
        """Parser should handle unclosed color tags gracefully."""
        text = "(<red>unclosed"
        ast = self.parse_text(text)
        # Should convert to text
        self.assertTrue(all(n.type == NodeType.TEXT for n in ast.children))

    def test_lists(self):
        """Parser should handle different types of list markers."""
        text = dedent("""
            * Bullet item
            # Number one
            > Arrow item
        """).strip()
        
        ast = self.parse_text(text)
        list_items = [n for n in ast.children if isinstance(n, ListItemNode)]
        
        self.assertEqual(len(list_items), 3)
        self.assertEqual([item.marker_type for item in list_items],
                        ['bullet', 'number', 'arrow'])

    def test_chinese_text(self):
        """Parser should handle Chinese text nodes."""
        text = "Hello 世界 World"
        ast = self.parse_text(text)
        
        # Should have text, Chinese, text nodes
        nodes = [n for n in ast.children if n.type in (NodeType.TEXT, NodeType.CHINESE)]
        self.assertEqual(len(nodes), 3)
        self.assert_node_type(nodes[1], NodeType.CHINESE)

    def test_urls_and_wikilinks(self):
        """Parser should handle URLs and wikilinks."""
        text = "Visit https://example.com and [[Wiki]]"
        ast = self.parse_text(text)
        
        special_nodes = [n for n in ast.children 
                        if n.type in (NodeType.URL, NodeType.WIKILINK)]
        self.assertEqual(len(special_nodes), 2)
        self.assert_node_type(special_nodes[0], NodeType.URL)
        self.assert_node_type(special_nodes[1], NodeType.WIKILINK)

    def test_unclosed_wikilink(self):
        """Parser should handle unclosed wikilinks gracefully."""
        text = "[[Unclosed link"
        ast = self.parse_text(text)
        # Should convert to text
        self.assertTrue(all(n.type == NodeType.TEXT for n in ast.children))

    def test_literal_blocks(self):
        """Parser should handle literal text blocks."""
        text = "Code: <<print('hello')>>"
        ast = self.parse_text(text)
        
        literal_nodes = [n for n in ast.children if n.type == NodeType.LITERAL]
        self.assertEqual(len(literal_nodes), 1)

    def test_emphasis(self):
        """Parser should handle emphasized text."""
        text = "This is *emphasized* text"
        ast = self.parse_text(text)
        
        emphasis_nodes = [n for n in ast.children if n.type == NodeType.EMPHASIS]
        self.assertEqual(len(emphasis_nodes), 1)
        self.assertEqual(emphasis_nodes[0].token.value, "emphasized")

    def test_complex_document(self):
        """Basic smoke test for complex documents."""
        text = dedent("""
            Introduction
            ----
            <red>Warning:
            * First point with some text.
            * Second with (<blue>note)
            
            Some [[Wiki]] text.

            <<<
            Quoted text
            More quotes
            >>>
            
            Final section with 中文
            ----
            Conclusion
        """).strip()
        
        ast = self.parse_text(text)
        self.assertGreater(len(ast.children), 1)
        
        # Verify presence of key node types
        expected_types = {
            NodeType.HR, NodeType.COLOR_BLOCK, 
            NodeType.LIST_ITEM, NodeType.MLQ,
            NodeType.CHINESE, NodeType.WIKILINK
        }
        for expected_type in expected_types:
            self.assertTrue(any(n.type == expected_type for n in ast.children),
                f"Expected to find node type {expected_type.name}")

if __name__ == '__main__':
      unittest.main()
