# React Compiler Tests

This directory contains integration tests for the React Compiler that compile actual sample widgets and verify their functionality.

## Overview

These tests are **expensive** and are separated from the main test suite because they:

- Compile actual React widgets using webpack
- Require Node.js and npm to be installed
- Install npm packages during testing
- Take significantly longer than unit tests
- May fail due to network issues or missing system dependencies

## Prerequisites

Before running these tests, ensure you have:

1. **Node.js** (version 14 or higher)
2. **npm** (comes with Node.js)

### Installation

**macOS (using Homebrew):**
```bash
brew install node
```

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install nodejs npm
```

**Windows:**
Download and install from [nodejs.org](https://nodejs.org/)

**Verify installation:**
```bash
node --version
npm --version
```

## Running the Tests

### Option 1: Dedicated Test Runner (Recommended)

Use the dedicated test runner for React Compiler tests:

```bash
# Run all React Compiler tests
python3 run_react_compiler_tests.py

# Run with verbose output
python3 run_react_compiler_tests.py --verbose

# Run specific tests
python3 run_react_compiler_tests.py --pattern "*basketball*"

# Run with coverage
python3 run_react_compiler_tests.py --coverage

# List available tests
python3 run_react_compiler_tests.py --list-tests

# Stop on first failure
python3 run_react_compiler_tests.py --fail-fast
```

### Option 2: Main Test Runner

Include React Compiler tests in the main test suite:

```bash
# Run only React Compiler tests
python3 run_tests.py --category react_compiler

# Run with other categories
python3 run_tests.py --category common --category react_compiler

# Run specific pattern
python3 run_tests.py --pattern "*sample*"
```

### Option 3: Direct pytest/unittest

```bash
# Using pytest (if installed)
python3 -m pytest src/tests/react_compiler/ -v

# Using unittest
python3 -m unittest discover src/tests/react_compiler/ -v
```

## Test Structure

### `test_sample_compilation.py`

Main integration test file that includes:

#### `TestSampleCompilation`
- **`test_basketball_sample_compilation()`** - Tests Basketball.jsx compilation
- **`test_trakaido_sample_compilation()`** - Tests Trakaido.jsx compilation  
- **`test_hook_detection_and_inlining()`** - Tests hook detection and inlining
- **`test_compilation_with_missing_dependencies()`** - Tests error handling
- **`test_export_handling()`** - Tests export pattern detection
- **`test_compiled_code_structure()`** - Tests output structure

#### `TestWidgetBuilderMethods`
- **`test_hook_import_detection()`** - Tests hook import detection
- **`test_export_handling_patterns()`** - Tests export handling

## What the Tests Verify

1. **Compilation Success**: The React Compiler can successfully compile sample widgets
2. **JavaScript Validity**: Compiled code is syntactically valid JavaScript
3. **Export Structure**: Widgets are properly exported with expected names
4. **Global Availability**: Compiled widgets are available as `window.WidgetName`
5. **UMD Structure**: Compiled code follows UMD module pattern
6. **Hook Processing**: Built-in hooks are detected and inlined correctly
7. **Dependency Handling**: Dependencies are properly managed
8. **Error Handling**: Graceful handling of missing dependencies

## Sample Widgets Tested

### Basketball.jsx
- Interactive basketball game widget
- Uses `useFullscreen` and `useGlobalSettings` hooks
- External dependency: `lucide-react`

### Trakaido.jsx  
- Lithuanian flashcard application
- Uses `useGlobalSettings` hook
- Complex state management and API integration

## Test Output

Successful tests will show:
```
Testing Basketball sample compilation...
Basketball dependencies: []
Basketball external dependencies: ['lucide-react']
Basketball sample compilation test passed!

Testing Trakaido sample compilation...
Trakaido dependencies: []
Trakaido external dependencies: []
Trakaido sample compilation test passed!
```

## Troubleshooting

### Common Issues

**Node.js/npm not found:**
```
✗ Node.js not found
Prerequisites not met. Please install Node.js and npm.
```
**Solution:** Install Node.js and npm as described in Prerequisites.

**Network issues during npm install:**
```
npm install failed: network timeout
```
**Solution:** Check internet connection, try again, or configure npm proxy if behind corporate firewall.

**Webpack build failures:**
```
webpack build failed: Module not found
```
**Solution:** Check that all dependencies are properly specified and available.

### Debug Mode

Run with verbose output to see detailed compilation steps:
```bash
python3 run_react_compiler_tests.py --verbose
```

This will show:
- Detected dependencies
- Hook inlining process
- npm install output
- webpack build output
- Detailed test progress

## Performance

These tests typically take:
- **Basketball compilation**: ~30-60 seconds
- **Trakaido compilation**: ~30-60 seconds  
- **Total test suite**: ~2-5 minutes

Time depends on:
- System performance
- Network speed (for npm installs)
- Whether npm packages are cached

## Coverage

Generate coverage reports:
```bash
python3 run_react_compiler_tests.py --coverage
```

This creates an HTML coverage report in `coverage_html_react_compiler/`.

## Integration with CI/CD

For CI/CD pipelines, consider:

1. **Separate job**: Run expensive tests in a separate CI job
2. **Caching**: Cache npm packages between runs
3. **Timeouts**: Set appropriate timeouts (5-10 minutes)
4. **Prerequisites**: Ensure Node.js/npm are available in CI environment

Example GitHub Actions step:
```yaml
- name: Setup Node.js
  uses: actions/setup-node@v3
  with:
    node-version: '18'
    
- name: Run React Compiler Tests
  run: python3 run_react_compiler_tests.py --verbose
  timeout-minutes: 10
```

## Contributing

When adding new sample widgets:

1. Add the `.jsx` file to `src/react_compiler/samples/`
2. Add a corresponding test method in `test_sample_compilation.py`
3. Follow the naming pattern: `test_{widget_name}_sample_compilation()`
4. Verify the widget exports the expected component name
5. Document any special dependencies or requirements

## Related Files

- `src/react_compiler/react_compiler.py` - Main React Compiler implementation
- `src/react_compiler/samples/` - Sample widget files
- `run_react_compiler_tests.py` - Dedicated test runner
- `run_tests.py` - Main test runner (includes react_compiler category)