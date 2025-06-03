#!/usr/bin/env python3
"""
Expensive React Compiler Integration Tests

This script runs the expensive React Compiler tests that:
- Compile actual sample widgets
- Require Node.js and npm
- Install npm packages during testing
- Run webpack builds
- Take significantly longer than unit tests

These tests are separated from the main test suite because they are:
1. Expensive in terms of time and resources
2. Require external dependencies (Node.js, npm)
3. May fail due to network issues or missing system dependencies

Usage:
    python3 run_react_compiler_tests.py [options]

Options:
    --verbose, -v    Enable verbose output
    --quiet, -q      Suppress non-essential output
    --pattern PATTERN Only run tests matching pattern
    --fail-fast, -x  Stop on first test failure
    --coverage       Enable coverage reporting
    --list-tests     List available tests without running them
"""

import sys
import os
import argparse
import unittest
import tempfile
import importlib.util
import subprocess
import logging
from typing import Optional

# Add src directory to Python path
project_root = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(project_root, 'src')
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

# Change working directory to src for imports
os.chdir(src_dir)


def check_prerequisites() -> bool:
    """Check if all prerequisites for React Compiler tests are available."""
    print("Checking prerequisites...")
    
    # Check Node.js
    try:
        result = subprocess.run(['node', '--version'], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✓ Node.js: {result.stdout.strip()}")
        else:
            print("✗ Node.js not found")
            return False
    except FileNotFoundError:
        print("✗ Node.js not found")
        return False
    
    # Check npm
    try:
        result = subprocess.run(['npm', '--version'], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✓ npm: {result.stdout.strip()}")
        else:
            print("✗ npm not found")
            return False
    except FileNotFoundError:
        print("✗ npm not found")
        return False
    
    # Check if samples directory exists
    samples_dir = os.path.join('react_compiler', 'samples')
    if os.path.exists(samples_dir):
        sample_files = [f for f in os.listdir(samples_dir) if f.endswith('.jsx')]
        print(f"✓ Found {len(sample_files)} sample files: {', '.join(sample_files)}")
    else:
        print(f"✗ Samples directory not found: {samples_dir}")
        return False
    
    print("All prerequisites met!")
    return True


def discover_react_compiler_tests() -> list:
    """Discover React Compiler test modules."""
    test_modules = []
    test_dir = os.path.join('tests', 'react_compiler')
    
    if not os.path.exists(test_dir):
        return test_modules
    
    for file in os.listdir(test_dir):
        if file.startswith('test_') and file.endswith('.py'):
            test_modules.append(os.path.join(test_dir, file))
    
    return test_modules


def run_react_compiler_tests(pattern: Optional[str] = None,
                            verbose: bool = False,
                            quiet: bool = False,
                            fail_fast: bool = False,
                            with_coverage: bool = False) -> bool:
    """Run React Compiler tests."""
    
    # Check prerequisites first
    if not check_prerequisites():
        print("\nPrerequisites not met. Please install Node.js and npm.")
        print("On macOS: brew install node")
        print("On Ubuntu: sudo apt-get install nodejs npm")
        print("On Windows: Download from https://nodejs.org/")
        return False
    
    print("\nRunning React Compiler tests...")
    
    # Set up test environment
    os.environ['TESTING'] = 'true'
    
    # Set up logging
    log_level = logging.DEBUG if verbose else logging.INFO if not quiet else logging.WARNING
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    try:
        # Initialize coverage if requested
        cov = None
        if with_coverage:
            try:
                import coverage
                cov = coverage.Coverage(source=['react_compiler'])
                cov.start()
            except ImportError:
                print("Warning: coverage package not found. Install with: pip install coverage")
                with_coverage = False
        
        # Discover test modules
        test_modules = discover_react_compiler_tests()
        
        if not test_modules:
            print("No React Compiler test modules found.")
            return True
        
        # Create test loader
        loader = unittest.TestLoader()
        if pattern:
            loader.testNamePatterns = [pattern]
        
        # Load tests from modules
        suite = unittest.TestSuite()
        for module_path in test_modules:
            module_name = os.path.splitext(os.path.basename(module_path))[0]
            
            if verbose:
                print(f"Loading tests from {module_name}")
            
            # Import module and add tests
            spec = importlib.util.spec_from_file_location(module_name, module_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            suite.addTests(loader.loadTestsFromModule(module))
        
        # Run tests
        verbosity = 0 if quiet else (2 if verbose else 1)
        runner = unittest.TextTestRunner(
            verbosity=verbosity,
            failfast=fail_fast,
            buffer=not verbose
        )
        
        print(f"\nRunning {suite.countTestCases()} React Compiler tests...\n")
        result = runner.run(suite)
        
        # Generate coverage report if enabled
        if with_coverage and cov:
            cov.stop()
            print("\nCoverage Report:")
            cov.report()
            
            # Generate HTML report
            html_dir = os.path.join(project_root, 'coverage_html_react_compiler')
            cov.html_report(directory=html_dir)
            print(f"HTML coverage report generated in: {html_dir}")
        
        # Print summary
        print(f"\nTest Summary:")
        print(f"Tests run: {result.testsRun}")
        print(f"Failures: {len(result.failures)}")
        print(f"Errors: {len(result.errors)}")
        print(f"Skipped: {len(result.skipped)}")
        
        if result.failures:
            print("\nFailures:")
            for test, traceback in result.failures:
                print(f"  {test}: {traceback.split('AssertionError:')[-1].strip()}")
        
        if result.errors:
            print("\nErrors:")
            for test, traceback in result.errors:
                print(f"  {test}: {traceback.split('Exception:')[-1].strip()}")
        
        return result.wasSuccessful()
        
    except Exception as e:
        print(f"Error running React Compiler tests: {e}")
        if verbose:
            import traceback
            traceback.print_exc()
        return False


def list_react_compiler_tests():
    """List available React Compiler tests."""
    test_modules = discover_react_compiler_tests()
    
    if not test_modules:
        print("No React Compiler test modules found.")
        return
    
    print("Available React Compiler test modules:")
    for module_path in test_modules:
        module_name = os.path.basename(module_path).replace('.py', '')
        print(f"  {module_name}")
        
        # Try to load module and list test methods
        try:
            spec = importlib.util.spec_from_file_location(module_name, module_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # Find test classes and methods
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (isinstance(attr, type) and 
                    issubclass(attr, unittest.TestCase) and 
                    attr != unittest.TestCase):
                    
                    test_methods = [method for method in dir(attr) 
                                  if method.startswith('test_')]
                    if test_methods:
                        print(f"    {attr.__name__}:")
                        for method in test_methods:
                            print(f"      {method}")
        except Exception as e:
            print(f"    (Error loading module: {e})")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Run expensive React Compiler integration tests',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                           # Run all React Compiler tests
  %(prog)s --verbose                 # Run with verbose output
  %(prog)s --pattern "*basketball*"  # Run only basketball-related tests
  %(prog)s --coverage                # Run with coverage reporting
  %(prog)s --list-tests              # List available tests
  %(prog)s --fail-fast               # Stop on first failure

Note: These tests require Node.js and npm to be installed.
        """ % {'prog': os.path.basename(__file__)}
    )
    
    parser.add_argument(
        '--pattern',
        help='Only run tests matching pattern (e.g., "*basketball*")'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose output'
    )
    
    parser.add_argument(
        '--quiet', '-q',
        action='store_true',
        help='Suppress non-essential output'
    )
    
    parser.add_argument(
        '--coverage',
        action='store_true',
        help='Enable coverage reporting'
    )
    
    parser.add_argument(
        '--fail-fast', '-x',
        action='store_true',
        help='Stop on first test failure'
    )
    
    parser.add_argument(
        '--list-tests',
        action='store_true',
        help='List available tests without running them'
    )
    
    args = parser.parse_args()
    
    try:
        if args.list_tests:
            list_react_compiler_tests()
            sys.exit(0)
        
        success = run_react_compiler_tests(
            pattern=args.pattern,
            verbose=args.verbose and not args.quiet,
            quiet=args.quiet,
            fail_fast=args.fail_fast,
            with_coverage=args.coverage
        )
        
        sys.exit(0 if success else 1)
        
    except KeyboardInterrupt:
        print("\nTest run interrupted by user", file=sys.stderr)
        sys.exit(130)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()