# JavaScript Unit Tests

This directory contains unit tests for JavaScript code in the Atacama project.

## Setup

The tests use Jest as the testing framework. To set up the testing environment:

1. Make sure you have Node.js installed
2. Run `npm install` in this directory to install dependencies

## Running Tests

To run all tests:

```bash
npm test
```

To run a specific test file:

```bash
npx jest path/to/test-file.js
```

## Test Coverage

To generate a test coverage report:

```bash
npx jest --coverage
```

This will create a `coverage` directory with detailed reports.

## Adding New Tests

When adding new tests:

1. Create a new test file with the `.test.js` extension
2. Follow the existing test patterns
3. Run the tests to ensure they pass

## Current Test Files

- `diff.test.js` - Tests for the DiffUtil class in `src/web/js/diff.js`