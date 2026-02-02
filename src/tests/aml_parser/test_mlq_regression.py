#!/usr/bin/python3

"""
Regression test for colored MLQ blocks in the parser.
Tests the feature where a color tag at the start of a line
followed by an MLQ block causes the entire MLQ to be colored.
"""

import unittest

from aml_parser.lexer import tokenize
from aml_parser.parser import parse, NodeType
from aml_parser.html_generator import generate_html


class ColoredMLQTest(unittest.TestCase):
    
    def test_basic_colored_mlq(self):
        """Test basic case: color tag at line start followed by MLQ."""
        input_text = "<red> <<< This is a red MLQ block\nWith multiple lines\nAnd content >>>"
        tokens = tokenize(input_text)
        ast = parse(tokens)
        
        # Verify AST structure
        self.assertEqual(len(ast.children), 1, "Should have exactly one child node")
        mlq_node = ast.children[0]
        self.assertEqual(mlq_node.type, NodeType.MLQ, "Node should be an MLQ")
        self.assertTrue(hasattr(mlq_node, 'color'), "MLQ should have a color attribute")
        self.assertEqual(mlq_node.color, 'red', "Color should be 'red'")
        
        # Test HTML generation
        html = generate_html(ast)
        self.assertIn('<div class="mlq color-red">', html, "HTML should include MLQ div")
        self.assertIn("This is a red MLQ block", html, "HTML should include MLQ content")
    
    def test_midline_color_mlq(self):
        """Test that mid-line color tag doesn't create a colored MLQ.

        When a color tag is NOT at line start:
        - It creates a line-level color block that extends to end of line
        - The MLQ markers (<<<, >>>) become text content inside the color block
        - The colored-MLQ syntax (<color> <<<...>>>) only applies at line start

        This is different from having a separate MLQ node - the parser design
        is that line-level color blocks consume until end of line.
        """
        input_text = "Some text <red> <<< This MLQ shouldn't be red >>>"
        tokens = tokenize(input_text)
        ast = parse(tokens)

        # Should have: TEXT, COLOR_BLOCK (containing the MLQ markers as text)
        self.assertEqual(len(ast.children), 2)
        self.assertEqual(ast.children[0].type, NodeType.TEXT)
        self.assertEqual(ast.children[1].type, NodeType.COLOR_BLOCK)

        # The color block should contain the MLQ markers as text, not as MLQ node
        color_block = ast.children[1]
        self.assertEqual(color_block.color, 'red')
        # Verify no MLQ node exists - MLQ markers are absorbed as text
        mlq_nodes = [n for n in ast.children if n.type == NodeType.MLQ]
        self.assertEqual(len(mlq_nodes), 0, "Mid-line color blocks absorb MLQ markers as text")
    
    def test_newline_between(self):
        """Test that newline between color tag and MLQ breaks the association."""
        input_text = "<red>\n<<< This MLQ should not be red >>>"
        tokens = tokenize(input_text)
        ast = parse(tokens)
        
        # Verify we have separate nodes for color and MLQ
        found_color = False
        found_mlq = False
        for node in ast.children:
            if node.type == NodeType.COLOR_BLOCK:
                found_color = True
            elif node.type == NodeType.MLQ:
                found_mlq = True
                self.assertFalse(hasattr(node, 'color'), "MLQ should NOT have a color attribute")
        
        self.assertTrue(found_color, "Should have a color node")
        self.assertTrue(found_mlq, "Should have an MLQ node")
    
    def test_multiple_mlqs(self):
        """Test multiple MLQs where only the first one is colored."""
        input_text = "<blue> <<< This MLQ should be blue >>>\n<<< This MLQ should not be blue >>>"
        tokens = tokenize(input_text)
        ast = parse(tokens)
        
        self.assertEqual(len(ast.children), 3)
        first_mlq = ast.children[0]
        self.assertEqual(ast.children[1].type, NodeType.NEWLINE, "Nodes should be separated by newline.")
        second_mlq = ast.children[2]
        
        self.assertEqual(first_mlq.type, NodeType.MLQ, "First node should be an MLQ")
        self.assertEqual(second_mlq.type, NodeType.MLQ, "Second node should be an MLQ")
        self.assertTrue(hasattr(first_mlq, 'color'), "First MLQ should have a color attribute")
        self.assertEqual(first_mlq.color, 'blue', "First MLQ color should be 'blue'")
        self.assertFalse(hasattr(second_mlq, 'color'), "Second MLQ should NOT have a color attribute")
        
        # Test HTML generation to ensure correct wrapping
        html = generate_html(ast)
        self.assertEqual(html.count('<div class="mlq color-blue">'), 1, "Should have exactly one blue colorblock")
    
    def test_multiple_color_names(self):
        """Test that all valid color names work with colored MLQs."""
        color_names = [
            'xantham', 'red', 'orange', 'blue', 'green', 'gray', 'hazel']
        
        for color in color_names:
            input_text = f"<{color}> <<< This is a {color} MLQ block >>>"
            tokens = tokenize(input_text)
            ast = parse(tokens)
            
            self.assertEqual(len(ast.children), 1, f"Should have one node for {color}")
            mlq_node = ast.children[0]
            self.assertEqual(mlq_node.type, NodeType.MLQ, f"Node should be MLQ for {color}")
            self.assertTrue(hasattr(mlq_node, 'color'), f"MLQ should have color for {color}")
            self.assertEqual(mlq_node.color, color, f"Color should be {color}")
            
            html = generate_html(ast)
            self.assertIn(f'<div class="mlq color-{color}">', html, f"HTML should include {color} block")


if __name__ == '__main__':
    unittest.main()
