#!/usr/bin/env python3
"""
PRESUBMIT checks for the Atacama project.
Currently checks:
- Python import correctness and organization
- Unused imports
- Third-party imports against requirements.txt
- Missing imports and undefined variables
"""

import argparse
import ast
import os
import sys
import pkgutil
from pathlib import Path
from typing import List, Set, Dict, Tuple, Optional
from contextlib import contextmanager

class Context:
    """Tracks scoping context during AST traversal."""
    def __init__(self):
        self.defined_names: Set[str] = set()
        self.used_names: Set[str] = set()
        self.undefined_names: Set[str] = set()
        self.comprehension_vars: Set[str] = set()
        self.in_comprehension = False

    @contextmanager
    def comprehension_scope(self):
        """Context manager for tracking comprehension scope."""
        prev = self.in_comprehension
        self.in_comprehension = True
        yield
        self.in_comprehension = prev

class SymbolTableVisitor(ast.NodeVisitor):
    """Visitor that builds a symbol table of defined names."""
    def __init__(self):
        self.ctx = Context()
        
        # Initialize with magic variables that are always defined
        self.ctx.defined_names.update([
            '__name__', '__file__', '__doc__', '__package__',
            '__path__', '__spec__', '__loader__', '__cached__',
            '__builtins__', '__import__', '__annotations__'
        ])

    def visit_ExceptHandler(self, node):
        """Handle exception handler variables."""
        # Add exception variable to defined names if present
        if node.name:
            self.ctx.defined_names.add(node.name)
        self.generic_visit(node)

    def visit_Name(self, node):
        """Handle variable names, tracking definition and usage."""
        if isinstance(node.ctx, ast.Store):
            self.ctx.defined_names.add(node.id)
        elif isinstance(node.ctx, ast.Load):
            self.ctx.used_names.add(node.id)
            if (node.id not in self.ctx.defined_names and 
                node.id not in self.ctx.comprehension_vars):
                self.ctx.undefined_names.add(node.id)
        self.generic_visit(node)

    def visit_Import(self, node):
        """Handle regular imports."""
        for alias in node.names:
            name = alias.asname or alias.name
            self.ctx.defined_names.add(name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        """Handle from-imports, including handling star imports."""
        for alias in node.names:
            if alias.name == '*':
                continue  # Skip star imports in analysis
            name = alias.asname or alias.name
            self.ctx.defined_names.add(name)
        self.generic_visit(node)

    def visit_FunctionDef(self, node):
        """Handle function definitions and their parameters."""
        self.ctx.defined_names.add(node.name)
        # Add function parameters
        for arg in node.args.args:
            self.ctx.defined_names.add(arg.arg)
        # Add kwonly arguments
        for arg in node.args.kwonlyargs:
            self.ctx.defined_names.add(arg.arg)
        # Add varargs and kwargs if present
        if node.args.vararg:
            self.ctx.defined_names.add(node.args.vararg.arg)
        if node.args.kwarg:
            self.ctx.defined_names.add(node.args.kwarg.arg)
        self.generic_visit(node)

    def visit_ClassDef(self, node):
        """Handle class definitions."""
        self.ctx.defined_names.add(node.name)
        self.generic_visit(node)

    def visit_ListComp(self, node):
        """Handle list comprehensions."""
        with self.ctx.comprehension_scope():
            for generator in node.generators:
                if isinstance(generator.target, ast.Name):
                    self.ctx.comprehension_vars.add(generator.target.id)
                elif isinstance(generator.target, (ast.Tuple, ast.List)):
                    for elt in generator.target.elts:
                        if isinstance(elt, ast.Name):
                            self.ctx.comprehension_vars.add(elt.id)
            self.generic_visit(node)

    def visit_SetComp(self, node):
        """Handle set comprehensions."""
        self.visit_ListComp(node)  # Same logic as list comprehensions

    def visit_DictComp(self, node):
        """Handle dictionary comprehensions."""
        self.visit_ListComp(node)  # Same logic as list comprehensions

    def visit_GeneratorExp(self, node):
        """Handle generator expressions."""
        self.visit_ListComp(node)  # Same logic as list comprehensions

    def visit_Lambda(self, node):
        """Handle lambda function arguments."""
        # Add all argument names to defined names
        for arg in node.args.args:
            self.ctx.defined_names.add(arg.arg)
        # Handle any default argument values
        if node.args.kwonlyargs:
            for arg in node.args.kwonlyargs:
                self.ctx.defined_names.add(arg.arg)
        if node.args.vararg:
            self.ctx.defined_names.add(node.args.vararg.arg)
        if node.args.kwarg:
            self.ctx.defined_names.add(node.args.kwarg.arg)
        self.generic_visit(node)

def get_stdlib_modules() -> Set[str]:
    """
    Get a set of all Python standard library module names.
    
    :return: Set of module names
    """
    stdlib_modules = set()
    
    # Get built-in module names from sys.modules
    for module_name, module in sys.modules.items():
        if not module_name.startswith('_'):  # Skip private modules
            if getattr(module, '__file__', None):
                if 'site-packages' not in str(module.__file__):
                    stdlib_modules.add(module_name.split('.')[0])
            else:
                stdlib_modules.add(module_name.split('.')[0])
    
    # Also check additional modules available via pkgutil
    for module in pkgutil.iter_modules():
        if not module.name.startswith('_'):  # Skip private modules
            stdlib_modules.add(module.name)
            
    return stdlib_modules

def get_requirements() -> Dict[str, str]:
    """
    Parse requirements.txt to get list of required packages with their import names.
    
    :return: Dict mapping import names to package names
    """
    # Common package name to import name mappings
    PACKAGE_TO_IMPORT = {
        'Flask': 'flask',
        'Werkzeug': 'werkzeug',
        'SQLAlchemy': 'sqlalchemy',
        'PyYAML': 'yaml',
        'Pillow': 'PIL',
        'beautifulsoup4': 'bs4',
        'python-dotenv': 'dotenv',
        'google-auth': 'google',
    }
    
    requirements = {}
    try:
        with open("requirements.txt", 'r') as f:
            for line in f:
                # Skip comments and empty lines
                line = line.strip()
                if line and not line.startswith('#'):
                    # Extract package name, removing version specifiers
                    package = line.split('==')[0].split('>=')[0].split('<=')[0].split('[')[0].strip()
                    
                    # Get the import name
                    import_name = PACKAGE_TO_IMPORT.get(package, package.lower())
                    requirements[import_name] = package
                    
    except FileNotFoundError:
        print("Warning: requirements.txt not found")
    return requirements

def get_python_files(root_dir: str, changed_only: bool = False) -> List[Path]:
    """
    Find Python files in the project.
    
    :param root_dir: Root directory to start search from
    :param changed_only: If True, only return files modified in current Git changes
    :return: List of Path objects for Python files
    """
    if changed_only:
        import subprocess
        try:
            # Get both staged and unstaged changes
            staged = subprocess.check_output(['git', 'diff', '--cached', '--name-only']).decode()
            unstaged = subprocess.check_output(['git', 'diff', '--name-only']).decode()
            
            # Combine and filter for Python files
            changed_files = set(staged.splitlines() + unstaged.splitlines())
            python_files = [Path(f) for f in changed_files if f.endswith('.py')]
            return sorted(python_files)
        except subprocess.CalledProcessError:
            print("Warning: Failed to get Git changes, checking all files instead")
            return get_python_files(root_dir, False)
    
    python_files = []
    for root, _, files in os.walk(root_dir):
        if any(part.startswith('.') or part == '__pycache__' for part in Path(root).parts):
            continue
        for file in files:
            if file.endswith('.py'):
                python_files.append(Path(root) / file)
    return sorted(python_files)

def check_imports(file_path: Path) -> List[str]:
    """
    Check imports in a Python file for correctness.
    Validates:
    - Import syntax
    - Relative import usage
    - Unused imports
    - Third-party imports against requirements.txt
    - Missing imports and undefined variables
    
    :param file_path: Path to the Python file to check
    :return: List of error messages, empty if no errors
    """
    errors = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        tree = ast.parse(content)
        
        # Get required packages and stdlib modules
        requirements = get_requirements()
        stdlib_modules = get_stdlib_modules()
        
        # Track imports and their usage
        imports = {}  # name -> node
        import_names = set()  # All imported names for checking usage
        
        # First pass: collect imports
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.Import):
                    for name in node.names:
                        imports[name.name] = node
                        import_names.add(name.asname or name.name)
                else:  # ImportFrom
                    if node.module:  # Handle "from . import x" case
                        imports[node.module] = node
                        for name in node.names:
                            if name.name != '*':
                                import_names.add(name.asname or name.name)
                                
                # Check for relative imports outside of tests
                if isinstance(node, ast.ImportFrom) and node.level > 0:
                    if not any(part.startswith('test_') for part in file_path.parts):
                        errors.append(f"Relative import found in non-test file: {file_path}")
                        
                # Check third-party imports against requirements
                if isinstance(node, ast.Import):
                    for name in node.names:
                        base_package = name.name.split('.')[0]
                        if base_package in stdlib_modules:
                            continue
                        if base_package.startswith(('common', 'web', 'parser', 'spaceship')) or base_package in ("constants",):
                            continue
                        if base_package not in requirements:
                            errors.append(f"Third-party import '{base_package}' not found in requirements.txt (package: {requirements.get(base_package.lower(), base_package)}): {file_path}")
                elif node.module:
                    base_package = node.module.split('.')[0]
                    if base_package in stdlib_modules:
                        continue  
                    if base_package.startswith(('common', 'web', 'parser', 'spaceship')) or base_package in ("constants",):
                        continue
                    if base_package not in requirements:
                        errors.append(f"Third-party import '{base_package}' not found in requirements.txt (package: {requirements.get(base_package.lower(), base_package)}): {file_path}")
        
        # Build symbol table and check for undefined variables
        symbol_visitor = SymbolTableVisitor()
        symbol_visitor.visit(tree)
        
        # Type checking imports that shouldn't trigger unused warnings
        type_checking_imports = {
            'Optional', 'List', 'Dict', 'Set', 'Tuple', 'Any', 'Enum',
            'Pattern', 'Match',
        }
        
        # Find unused imports, excluding type checking imports
        unused_imports = (import_names - symbol_visitor.ctx.used_names - {'_'} - type_checking_imports)
        for name in unused_imports:
            errors.append(f"Unused import '{name}' in {file_path}")
            
        # Filter out some common builtins and known good names
        builtin_names = set(dir(__builtins__))
        common_names = {
            'self', 'cls', 'kwargs', 'args',  # Common parameter names
            'Base',  # SQLAlchemy
            'logger',  # Logging
        }
        undefined = symbol_visitor.ctx.undefined_names - builtin_names - common_names
        
        # Report undefined variables
        for name in undefined:
            errors.append(f"Undefined variable '{name}' used in {file_path}")
                        
    except SyntaxError as e:
        errors.append(f"Syntax error in {file_path}: {str(e)}")
    except Exception as e:
        errors.append(f"Error processing {file_path}: {str(e)}")
        
    return errors

def main() -> int:
    """
    Run all PRESUBMIT checks.
    
    :return: 0 if all checks pass, 1 if any fail
    """

    # CMD args
    parser = argparse.ArgumentParser(description='Run PRESUBMIT checks.')
    parser.add_argument('--files', choices=['all', 'changed'],
                   default='all',
                   help='Which files to check: all Python files or only changed ones')

    args = parser.parse_args()

    # Get project root directory (parent of this script)
    root_dir = Path(__file__).parent / "src"
    
    check_changed_only = (args.files == 'changed')
    # Find all Python files
    python_files = get_python_files(root_dir, changed_only=check_changed_only)
    
    # Track all errors
    all_errors = []
    
    # Run import checks
    for file_path in python_files:
        errors = check_imports(file_path)
        all_errors.extend(errors)
    
    # Report results
    if all_errors:
        print("\nPRESUBMIT FAILED! Issues found:")
        for error in all_errors:
            print(f"  • {error}")
        return 1
    
    print("\nPRESUBMIT PASSED - All checks successful!")
    return 0

if __name__ == '__main__':
    sys.exit(main())
