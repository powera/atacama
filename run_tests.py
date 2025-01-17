#!/usr/bin/python3

import unittest
import sys
import os
import tempfile
import importlib.util
from typing import List, Optional
import coverage
import argparse

def setup_test_environment():
    """Configure environment for testing."""
    # Use temp SQLite database for testing
    temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
    os.environ['TEST_DB_PATH'] = temp_db.name
    
    # Set testing flag
    os.environ['TESTING'] = 'true'
    
    # Add src directory to Python path
    project_root = os.path.dirname(os.path.abspath(__file__))
    src_dir = os.path.join(project_root, 'src')
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)
    
    return temp_db.name

def cleanup_test_environment(db_path: str):
    """Clean up test environment."""
    try:
        os.unlink(db_path)
    except Exception as e:
        print(f"Warning: Could not remove test database: {e}")

def discover_test_modules() -> dict:
    """
    Find all test modules organized by category.
    
    Returns:
        Dict mapping category names to lists of test module paths
    """
    categories = {
        'common': [],
        'web': [],
        'parser': []
    }
    
    project_root = os.path.dirname(os.path.abspath(__file__))
    test_dir = os.path.join(project_root, 'src', 'tests')
    
    # Scan test directories
    for category in categories:
        category_dir = os.path.join(test_dir, category)
        if not os.path.exists(category_dir):
            continue
            
        for file in os.listdir(category_dir):
            if file.startswith('test_') and file.endswith('.py'):
                categories[category].append(
                    os.path.join(category_dir, file)
                )
    
    return categories

def run_test_suite(categories: Optional[List[str]] = None,
                   pattern: Optional[str] = None,
                   verbose: bool = False,
                   with_coverage: bool = False) -> bool:
    """
    Run test suite with optional filtering.
    
    Args:
        categories: List of categories to test (common, web, parser)
        pattern: Optional test name pattern to filter by
        verbose: Enable verbose output
        with_coverage: Enable coverage reporting
    
    Returns:
        bool: True if all tests passed
    """
    # Set up test database
    db_path = setup_test_environment()
    
    try:
        # Initialize coverage if requested
        cov = None
        if with_coverage:
            cov = coverage.Coverage()
            cov.start()
        
        # Discover tests
        all_tests = discover_test_modules()
        
        # Filter by requested categories
        if categories:
            test_modules = []
            for category in categories:
                if category in all_tests:
                    test_modules.extend(all_tests[category])
        else:
            test_modules = [
                module for modules in all_tests.values()
                for module in modules
            ]
        
        # Create test loader
        loader = unittest.TestLoader()
        if pattern:
            loader.testNamePatterns = [pattern]
        
        # Load tests from modules
        suite = unittest.TestSuite()
        for module_path in test_modules:
            # Get module name from path
            module_name = os.path.splitext(
                os.path.basename(module_path)
            )[0]
            
            if verbose:
                print(f"Loading tests from {module_name}")
            
            # Import module and add tests
            spec = importlib.util.spec_from_file_location(
                module_name, module_path
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            suite.addTests(loader.loadTestsFromModule(module))
        
        # Run tests
        runner = unittest.TextTestRunner(
            verbosity=2 if verbose else 1
        )
        result = runner.run(suite)
        
        # Generate coverage report if enabled
        if with_coverage:
            cov.stop()
            cov.report()
            cov.html_report(directory='coverage_html')
        
        return result.wasSuccessful()
        
    finally:
        cleanup_test_environment(db_path)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Run Atacama test suite'
    )
    
    parser.add_argument(
        '--category',
        choices=['common', 'web', 'parser'],
        action='append',
        help='Test categories to run (can specify multiple)'
    )
    
    parser.add_argument(
        '--pattern',
        help='Only run tests matching pattern'
    )
    
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose output'
    )
    
    parser.add_argument(
        '--coverage',
        action='store_true',
        help='Enable coverage reporting'
    )
    
    args = parser.parse_args()
    
    success = run_test_suite(
        categories=args.category,
        pattern=args.pattern,
        verbose=args.verbose,
        with_coverage=args.coverage
    )
    
    sys.exit(0 if success else 1)
