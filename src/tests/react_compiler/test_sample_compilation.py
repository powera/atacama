#!/usr/bin/env python3
"""
Expensive integration tests for React Compiler using sample widgets.

These tests compile actual sample widgets and verify that:
1. The compilation process succeeds
2. The compiled code exports the expected objects at the expected names
3. The compiled code is syntactically valid JavaScript

These tests are marked as "expensive" because they:
- Require Node.js and npm to be installed
- Install npm packages during testing
- Run webpack builds
- Take significantly longer than unit tests

Run these tests separately with:
    python3 run_tests.py --pattern "*sample*"
    python3 -m pytest src/tests/react_compiler/test_sample_compilation.py -v
"""

import unittest
import os
import tempfile
import shutil
import re
import subprocess
from typing import Dict, List, Tuple
import logging

# Import the React Compiler
from react_compiler.react_compiler import WidgetBuilder

# Set up logging for tests
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TestSampleCompilation(unittest.TestCase):
    """Test compilation of sample React widgets."""
    
    @classmethod
    def setUpClass(cls):
        """Set up test environment once for all tests."""
        cls.samples_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'react_compiler', 'samples')
        cls.samples_dir = os.path.abspath(cls.samples_dir)
        
        # Verify samples directory exists
        if not os.path.exists(cls.samples_dir):
            raise unittest.SkipTest(f"Samples directory not found: {cls.samples_dir}")
        
        # Check if Node.js and npm are available
        try:
            subprocess.run(['node', '--version'], capture_output=True, check=True)
            subprocess.run(['npm', '--version'], capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            raise unittest.SkipTest("Node.js and npm are required for React Compiler tests")
        
        # Create a temporary build directory for all tests
        cls.build_dir = tempfile.mkdtemp(prefix='react_compiler_test_')
        cls.widget_builder = WidgetBuilder(build_dir=cls.build_dir)
        
        logger.info(f"Test setup complete. Build dir: {cls.build_dir}")
    
    @classmethod
    def tearDownClass(cls):
        """Clean up test environment."""
        if hasattr(cls, 'build_dir') and os.path.exists(cls.build_dir):
            shutil.rmtree(cls.build_dir, ignore_errors=True)
            logger.info(f"Cleaned up build dir: {cls.build_dir}")
    
    def setUp(self):
        """Set up for each test."""
        self.maxDiff = None  # Show full diff on assertion failures
    
    def _load_sample_file(self, filename: str) -> str:
        """Load a sample file and return its content."""
        file_path = os.path.join(self.samples_dir, filename)
        self.assertTrue(os.path.exists(file_path), f"Sample file not found: {file_path}")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    
    def _extract_expected_export_name(self, widget_code: str) -> str:
        """Extract the expected export name from widget code."""
        # Look for "export default ComponentName"
        default_export_match = re.search(r'export\s+default\s+(\w+)', widget_code)
        if default_export_match:
            return default_export_match.group(1)
        
        # Look for function/const declarations that might be exported
        function_match = re.search(r'const\s+(\w+)\s*=\s*\(\s*\)\s*=>', widget_code)
        if function_match:
            return function_match.group(1)
        
        # Fallback: look for any function declaration
        func_decl_match = re.search(r'function\s+(\w+)', widget_code)
        if func_decl_match:
            return func_decl_match.group(1)
        
        return None
    
    def _extract_dependencies_from_imports(self, widget_code: str) -> Tuple[List[str], List[str]]:
        """Extract dependencies from import statements."""
        dependencies = []
        external_dependencies = []
        
        # Find all import statements
        import_pattern = r"import\s+.*?\s+from\s+['\"]([^'\"]+)['\"]"
        imports = re.findall(import_pattern, widget_code)
        
        for imp in imports:
            # Skip relative imports (hooks)
            if imp.startswith('./'):
                continue
            # Skip React imports (handled by default)
            if imp in ['react', 'react-dom']:
                continue
            
            # Common external libraries that should be treated as external
            if imp in ['lucide-react', 'recharts', 'lodash', 'd3']:
                external_dependencies.append(imp)
            else:
                dependencies.append(imp)
        
        return dependencies, external_dependencies
    
    def _validate_compiled_javascript(self, compiled_code: str) -> bool:
        """Validate that the compiled code is syntactically valid JavaScript."""
        # Create a temporary file with the compiled code
        with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False) as f:
            f.write(compiled_code)
            temp_file = f.name
        
        try:
            # Use Node.js to check syntax
            result = subprocess.run(
                ['node', '--check', temp_file],
                capture_output=True,
                text=True
            )
            return result.returncode == 0
        except Exception:
            return False
        finally:
            os.unlink(temp_file)
    
    def _check_global_export(self, compiled_code: str, widget_name: str) -> bool:
        """Check if the compiled code properly exports the widget globally."""
        # Look for the global assignment pattern
        global_pattern = rf'window\.{widget_name}\s*='
        return bool(re.search(global_pattern, compiled_code))
    
    def _check_umd_export(self, compiled_code: str, widget_name: str) -> bool:
        """Check if the compiled code has UMD export structure."""
        # Look for UMD library pattern
        umd_pattern = rf'Widget_{widget_name}'
        return bool(re.search(umd_pattern, compiled_code))
    
    def test_basketball_sample_compilation(self):
        """Test compilation of Basketball.jsx sample."""
        logger.info("Testing Basketball sample compilation...")
        
        # Load the sample
        widget_code = self._load_sample_file('Basketball.jsx')
        widget_name = 'BasketballWidget'  # Will rename BasketballGame -> BasketballWidget
        
        # Extract dependencies
        dependencies, external_dependencies = self._extract_dependencies_from_imports(widget_code)
        logger.info(f"Basketball dependencies: {dependencies}")
        logger.info(f"Basketball external dependencies: {external_dependencies}")
        
        # Compile the widget
        success, compiled_code, error_message = self.widget_builder.build_widget(
            widget_code=widget_code,
            widget_name=widget_name,
            dependencies=dependencies,
            external_dependencies=external_dependencies
        )
        
        # Assert compilation succeeded
        self.assertTrue(success, f"Basketball compilation failed: {error_message}")
        self.assertIsNotNone(compiled_code, "Compiled code should not be None")
        self.assertNotEqual(compiled_code.strip(), "", "Compiled code should not be empty")
        
        # Validate JavaScript syntax
        self.assertTrue(
            self._validate_compiled_javascript(compiled_code),
            "Compiled Basketball code should be valid JavaScript"
        )
        
        # Check that the widget is exported globally
        self.assertTrue(
            self._check_global_export(compiled_code, widget_name),
            f"Basketball widget should be exported as window.{widget_name}"
        )
        
        # Check UMD export structure
        self.assertTrue(
            self._check_umd_export(compiled_code, widget_name),
            f"Basketball widget should have UMD export structure Widget_{widget_name}"
        )
        
        # Check that the compiled code contains expected metadata
        self.assertIn(f"Widget: {widget_name}", compiled_code)
        if external_dependencies:
            self.assertIn("External dependencies:", compiled_code)
        
        logger.info("Basketball sample compilation test passed!")
    
    def test_trakaido_sample_compilation(self):
        """Test compilation of Trakaido.jsx sample."""
        logger.info("Testing Trakaido sample compilation...")
        
        # Load the sample
        widget_code = self._load_sample_file('Trakaido.jsx')
        widget_name = 'TrakaidoWidget'  # Will rename FlashCardApp -> TrakaidoWidget
        
        # Extract dependencies
        dependencies, external_dependencies = self._extract_dependencies_from_imports(widget_code)
        logger.info(f"Trakaido dependencies: {dependencies}")
        logger.info(f"Trakaido external dependencies: {external_dependencies}")
        
        # Compile the widget
        success, compiled_code, error_message = self.widget_builder.build_widget(
            widget_code=widget_code,
            widget_name=widget_name,
            dependencies=dependencies,
            external_dependencies=external_dependencies
        )
        
        # Assert compilation succeeded
        self.assertTrue(success, f"Trakaido compilation failed: {error_message}")
        self.assertIsNotNone(compiled_code, "Compiled code should not be None")
        self.assertNotEqual(compiled_code.strip(), "", "Compiled code should not be empty")
        
        # Validate JavaScript syntax
        self.assertTrue(
            self._validate_compiled_javascript(compiled_code),
            "Compiled Trakaido code should be valid JavaScript"
        )
        
        # Check that the widget is exported globally
        self.assertTrue(
            self._check_global_export(compiled_code, widget_name),
            f"Trakaido widget should be exported as window.{widget_name}"
        )
        
        # Check UMD export structure
        self.assertTrue(
            self._check_umd_export(compiled_code, widget_name),
            f"Trakaido widget should have UMD export structure Widget_{widget_name}"
        )
        
        # Check that the compiled code contains expected metadata
        self.assertIn(f"Widget: {widget_name}", compiled_code)
        if external_dependencies:
            self.assertIn("External dependencies:", compiled_code)
        
        logger.info("Trakaido sample compilation test passed!")
    
    def test_hook_detection_and_inlining(self):
        """Test that hooks are properly detected and inlined."""
        logger.info("Testing hook detection and inlining...")
        
        # Load Basketball sample which uses hooks
        widget_code = self._load_sample_file('Basketball.jsx')
        
        # Check that hooks are detected
        hooks_needed = self.widget_builder._detect_hook_imports(widget_code)
        self.assertIsInstance(hooks_needed, list)
        
        # Basketball should use useFullscreen and useGlobalSettings
        expected_hooks = ['useFullscreen', 'useGlobalSettings']
        for hook in expected_hooks:
            self.assertIn(hook, hooks_needed, f"Hook {hook} should be detected in Basketball sample")
        
        logger.info(f"Detected hooks: {hooks_needed}")
        
        # Test hook inlining
        prepared_code = self.widget_builder._prepare_widget_code_with_hooks(widget_code, hooks_needed)
        
        # The prepared code should no longer have relative imports for hooks
        self.assertNotIn("from './useFullscreen'", prepared_code)
        self.assertNotIn("from './useGlobalSettings'", prepared_code)
        
        # But should contain the hook implementations
        self.assertIn("useFullscreen", prepared_code)
        self.assertIn("useGlobalSettings", prepared_code)
        
        logger.info("Hook detection and inlining test passed!")
    
    def test_compilation_with_missing_dependencies(self):
        """Test compilation behavior with missing dependencies."""
        logger.info("Testing compilation with missing dependencies...")
        
        # Create a simple widget with a non-existent dependency
        widget_code = """
import React from 'react';
import { NonExistentLibrary } from 'non-existent-library';

const TestWidget = () => {
    return <div>Test</div>;
};

export default TestWidget;
"""
        
        widget_name = 'TestWidget'
        dependencies = ['non-existent-library']
        
        # This should still succeed but log warnings
        success, compiled_code, error_message = self.widget_builder.build_widget(
            widget_code=widget_code,
            widget_name=widget_name,
            dependencies=dependencies
        )
        
        # The compilation might fail due to missing dependency, which is expected
        # We're mainly testing that the system handles it gracefully
        if not success:
            self.assertIn("non-existent-library", error_message.lower())
        
        logger.info("Missing dependencies test completed!")
    
    def test_export_handling(self):
        """Test that different export patterns are handled correctly."""
        logger.info("Testing export handling...")
        
        # Test with Basketball sample
        basketball_code = self._load_sample_file('Basketball.jsx')
        expected_export = self._extract_expected_export_name(basketball_code)
        self.assertEqual(expected_export, 'BasketballGame')
        
        # Test with Trakaido sample
        trakaido_code = self._load_sample_file('Trakaido.jsx')
        expected_export = self._extract_expected_export_name(trakaido_code)
        self.assertEqual(expected_export, 'FlashCardApp')
        
        logger.info("Export handling test passed!")
    
    def test_compiled_code_structure(self):
        """Test the structure of compiled code."""
        logger.info("Testing compiled code structure...")
        
        # Use a simple widget for this test
        widget_code = self._load_sample_file('Basketball.jsx')
        widget_name = 'BasketballWidget'
        
        success, compiled_code, error_message = self.widget_builder.build_widget(
            widget_code=widget_code,
            widget_name=widget_name,
            dependencies=[],
            external_dependencies=['lucide-react']
        )
        
        self.assertTrue(success, f"Compilation failed: {error_message}")
        
        # Check code structure
        lines = compiled_code.split('\n')
        
        # Should start with comment header
        self.assertTrue(any('Widget:' in line for line in lines[:10]))
        
        # Should have IIFE wrapper
        self.assertIn('(function() {', compiled_code)
        
        # Should have global assignment
        self.assertIn(f'window.{widget_name}', compiled_code)
        
        # Should end IIFE
        self.assertIn('})();', compiled_code)
        
        logger.info("Compiled code structure test passed!")


class TestWidgetBuilderMethods(unittest.TestCase):
    """Test individual methods of WidgetBuilder class."""
    
    def setUp(self):
        """Set up for each test."""
        self.build_dir = tempfile.mkdtemp(prefix='widget_builder_test_')
        self.widget_builder = WidgetBuilder(build_dir=self.build_dir)
    
    def tearDown(self):
        """Clean up after each test."""
        if os.path.exists(self.build_dir):
            shutil.rmtree(self.build_dir, ignore_errors=True)
    
    def test_hook_import_detection(self):
        """Test hook import detection."""
        test_code = """
import React, { useState } from 'react';
import { useFullscreen } from './useFullscreen';
import { useGlobalSettings } from './useGlobalSettings';
import { SomeComponent } from 'some-library';
"""
        
        hooks = self.widget_builder._detect_hook_imports(test_code)
        self.assertIn('useFullscreen', hooks)
        self.assertIn('useGlobalSettings', hooks)
        self.assertEqual(len(hooks), 2)
    
    def test_export_handling_patterns(self):
        """Test different export patterns."""
        # Test default export - should rename component to widget name
        code1 = "export default MyComponent;"
        result1 = self.widget_builder._handle_exports(code1, "MyWidget")
        self.assertIn("export default MyWidget", result1)
        
        # Test function component - should rename both definition and export
        code2 = """
const MyComponent = () => {
    return <div>Hello</div>;
};
export default MyComponent;
"""
        result2 = self.widget_builder._handle_exports(code2, "MyWidget")
        self.assertIn("const MyWidget =", result2)
        self.assertIn("export default MyWidget", result2)
        
        # Test when component name already matches widget name
        code3 = """
const MyWidget = () => {
    return <div>Hello</div>;
};
export default MyWidget;
"""
        result3 = self.widget_builder._handle_exports(code3, "MyWidget")
        self.assertIn("const MyWidget =", result3)
        self.assertIn("export default MyWidget", result3)
        
        # Test code without export - should add one
        code4 = """
const SomeComponent = () => {
    return <div>Hello</div>;
};
"""
        result4 = self.widget_builder._handle_exports(code4, "MyWidget")
        self.assertIn("export default MyWidget", result4)


if __name__ == '__main__':
    # Configure logging for standalone execution
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Run tests
    unittest.main(verbosity=2)