# CLAUDE.md - AI Assistant Guide for Atacama

This document provides comprehensive guidance for AI assistants working with the Atacama codebase.

Look at .agents/ for more detailed information about other repos used with
this one.

## Project Overview

Atacama is a multi-purpose web application consisting of three main components:

1. **Blog Server (Atacama CMS)**: A semantic web publishing platform for sharing richly formatted messages, articles, and interactive React widgets with custom markup language support
2. **Trakaido Stats API**: A backend API for tracking Lithuanian language learning statistics and flashcard progress
3. **Spaceship Daemon**: A lightweight proof-of-life server that serves XPlanet Earth images

## Architecture

### Technology Stack

- **Backend**: Python 3.9+ with Flask
- **Database**: SQLAlchemy (PostgreSQL/SQLite)
- **Web Server**: Waitress (production), Flask dev server (development)
- **Frontend**: Custom JavaScript with React widget system
- **Widget Compiler**: Node.js-based React/Webpack compilation system
- **Configuration**: TOML files for channels, domains, and admin settings

### Project Structure

```
atacama/
├── config/                      # TOML configuration files
│   ├── channels.toml           # Channel definitions and access levels
│   ├── domains.toml            # Multi-domain configuration and themes
│   ├── admin.toml              # Admin user configuration
│   └── languages.toml          # Language support configuration
├── data/                       # Runtime data directory
├── scripts/                    # Utility scripts
├── tools/                      # Development and migration tools
│   └── guid_migration/         # GUID migration utilities
├── src/
│   ├── aml_parser/             # Atacama Markup Language parser
│   ├── common/                 # Shared utilities and infrastructure
│   │   ├── base/               # Logging and request handling
│   │   ├── config/             # Configuration management
│   │   └── llm/                # LLM integration for widget generation
│   ├── models/                 # SQLAlchemy database models
│   │   ├── database.py         # Database initialization
│   │   ├── messages.py         # Content models
│   │   ├── users.py            # User models
│   │   └── quotes.py           # Quote tracking models
│   ├── react_compiler/         # React widget compilation system
│   │   ├── react_compiler.py   # Main compiler logic
│   │   ├── js/                 # Built-in React hooks
│   │   ├── samples/            # Sample widgets and utilities
│   │   └── lib.py              # Compiler library functions
│   ├── spaceship/              # XPlanet image server
│   │   ├── server.py           # Spaceship daemon
│   │   └── nginx.conf          # Nginx configuration for spaceship
│   ├── atacama/                # Core Atacama web server
│   │   ├── server.py           # Main Flask application
│   │   ├── blueprints/         # Core Flask blueprints
│   │   │   ├── auth.py         # OAuth and authentication
│   │   │   ├── errors.py       # Error handlers
│   │   │   ├── debug.py        # Debug utilities
│   │   │   ├── nav.py          # Navigation
│   │   │   └── static.py       # Static file serving
│   │   ├── decorators/         # Flask route decorators
│   │   │   ├── auth.py         # Authentication decorators
│   │   │   └── navigation.py   # Navigation decorators
│   │   ├── templates/          # Jinja2 templates
│   │   │   └── layouts/        # Base templates
│   │   ├── css/                # Stylesheets
│   │   ├── js/                 # Client-side JavaScript
│   │   │   ├── atacama.js      # Main client script
│   │   │   ├── lithuanianApi.js # Trakaido API client
│   │   │   └── third_party/    # Third-party libraries (React, etc.)
│   │   ├── static/             # Static assets
│   │   └── nginx.conf          # Nginx configuration
│   ├── blog/                   # Blog/CMS module
│   │   └── blueprints/         # Blog Flask blueprints
│   │       ├── content.py      # Content viewing
│   │       ├── article.py      # Article rendering
│   │       ├── submit.py       # Content submission
│   │       ├── widgets.py      # Widget management and compilation
│   │       ├── feeds.py        # RSS/Atom feeds
│   │       ├── quotes.py       # Quote collection
│   │       ├── statistics.py   # Content statistics
│   │       ├── admin.py        # Admin interface
│   │       └── shared.py       # Shared blog utilities
│   ├── tests/                  # Test suite
│   │   ├── common/             # Common module tests
│   │   ├── atacama/            # Atacama server tests
│   │   ├── blog/               # Blog module tests
│   │   ├── aml_parser/         # Parser tests
│   │   ├── react_compiler/     # React compiler tests
│   │   └── trakaido/           # Trakaido API tests
│   ├── trakaido/               # Trakaido Lithuanian language learning API
│   │   └── blueprints/         # Trakaido Flask blueprints
│   │       ├── userstats.py    # User statistics tracking
│   │       ├── userconfig_v2.py # User configuration (consolidated API)
│   │       ├── audio.py        # Audio file serving
│   │       ├── stats_schema.py # Stats data schema
│   │       ├── stats_snapshots.py # Historical snapshots
│   │       ├── nonce_utils.py  # Nonce authentication utilities
│   │       ├── date_utils.py   # Date handling utilities
│   │       ├── shared.py       # Shared utilities and blueprint
│   │       └── trakaido_tools.py # Utility functions
│   ├── util/                   # Utility scripts
│   └── constants.py            # Application-wide constants
├── launch.py                   # Main entry point (multi-mode launcher)
├── local_server.sh             # Local development server script
├── requirements.txt            # Python dependencies
├── run_tests.py                # Main test runner
├── run_react_compiler_tests.py # React compiler test runner
├── PRESUBMIT.py                # Pre-commit validation checks
├── README.md                   # User documentation
└── INSTALL.md                  # Production installation guide
```

## Key Components

### 1. Atacama Markup Language (AML)

Location: `src/aml_parser/`

A custom semantic markup language with color-coded tags that convey meaning:

- `<xantham>` - Sarcastic/overconfident tone
- `<red>` - Forceful statements
- `<orange>` - Counterpoints
- `<quote>` - Quoted material
- `<green>` - Technical content
- `<teal>` - AI-generated content
- `<blue>` - Voice from beyond
- `<violet>` - Serious announcements
- `<music>` - Musical content
- `<mogue>` - Actions taken
- `<gray>` - Past stories
- `<hazel>` - Storytelling

Additional features:
- `*text*` for emphasis
- `[[Page Title]]` for wiki-style links
- `<< literal >>` for monospace/code
- Chinese text with automatic pinyin annotations
- Chess notation rendering
- YouTube URL embedding
- Multi-line blocks with `<<<` and `>>>`

### 2. React Widget System

Location: `src/react_compiler/`, `src/blog/blueprints/widgets.py`

A complete React widget development and compilation system:

**Features:**
- Write React components with full hook support
- Automatic dependency detection and bundling
- Built-in custom hooks (useFullscreen, useGlobalSettings)
- Webpack-based compilation to UMD bundles
- Integration with Atacama content

**Supported Libraries:**
- Recharts, Lodash, Axios, D3, Date-fns, Lucide React

**Sample Widgets:**
- Basketball.jsx - Interactive game
- Trakaido.jsx - Lithuanian flashcards
- MathQuiz.jsx - Math quiz
- UnitConversion.jsx - Unit converter

### 3. Channel System

Location: `config/channels.toml`, `src/common/config/`

**Access Levels:**
- `public` - Accessible to all users
- `private` - Requires authentication
- `restricted` - Requires admin privileges

**Channel Groups:**
- Recreation, Media, Civics, Religion, Technology, Atacama, Personal, General

### 4. Multi-Domain Support

Location: `config/domains.toml`

- Different domains can access different channel subsets
- Per-domain theming support
- Domain-specific configurations (e.g., auto-archiving)

### 5. Trakaido Stats API

Location: `src/trakaido/blueprints/`

A comprehensive API for tracking language learning progress:

**Key Endpoints:**
- User statistics tracking
- User configuration management
- Audio file serving for pronunciation
- Historical stats snapshots
- Stats schema validation

**Features:**
- Nonce-based authentication
- Cross-domain cookie sharing (*.trakaido.com)
- Flashcard progress tracking
- Multiple stat types (vocabulary, flashcards, etc.)

### 6. Spaceship Daemon

Location: `src/spaceship/`

A lightweight proof-of-life server that serves XPlanet Earth images:

**Purpose:**
- Visual server status indicator
- Serves dynamically updated Earth images
- Can be configured with xplanet.conf

## Development Workflows

### Setting Up Development Environment

```bash
# Clone repository
git clone <repository-url>
cd atacama

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt

# Install Node.js dependencies (for React compiler)
# Ensure Node.js 14+ and npm are installed

# Set up configuration files
# Edit config/channels.toml, config/domains.toml as needed

# Create authentication secret
echo "your-dev-secret" > ~/.atacama_secret
chmod 600 ~/.atacama_secret
```

### Running the Application

```bash
# Development mode - all services
python3 launch.py

# Run specific service
python3 launch.py --mode web --port 5000  # Blog server only
python3 launch.py --mode spaceship --port 8000  # Spaceship only

# Or use the convenience script
./local_server.sh
```

### Testing

```bash
# Run all tests
python3 run_tests.py

# Run specific test category
python3 run_tests.py --category common
python3 run_tests.py --category web
python3 run_tests.py --category aml_parser

# Run React compiler tests (requires Node.js)
python3 run_react_compiler_tests.py

# Run with coverage
python3 run_tests.py --coverage

# Run with verbose output
python3 run_tests.py --verbose

# Run specific test pattern
python3 run_tests.py --pattern "test_auth*"

# Fail fast (stop on first failure)
python3 run_tests.py --fail-fast
```

### Pre-commit Checks

```bash
# Run PRESUBMIT checks (required before committing)
python3 PRESUBMIT.py

# Check only changed files
python3 PRESUBMIT.py --files changed
```

**What PRESUBMIT.py checks:**
- Import correctness and organization
- Unused imports
- Third-party imports against requirements.txt
- Missing imports and undefined variables
- No relative imports outside test files

## Code Conventions

### Import Organization

1. Standard library imports first
2. Third-party imports second
3. Local imports last
4. Alphabetically sorted within each group
5. No relative imports (except in test files)
6. All third-party imports must be in requirements.txt

### Python Style

- Follow PEP 8 guidelines
- Use type hints where beneficial
- Document complex functions with docstrings
- Prefer explicit over implicit

### File Naming

- Snake_case for Python files
- Test files: `test_*.py`
- Blueprint files organized by feature area

### Database Models

Location: `src/models/`

- Use SQLAlchemy ORM
- Models in separate files by domain (messages, users, quotes)
- Database initialization in `database.py`
- Support both PostgreSQL and SQLite

### Blueprint Organization

Blueprints are organized by functional area:
- `core/` - Cross-cutting concerns (auth, errors, navigation)
- `blog/` - Content management and viewing
- `trakaido/` - Stats API endpoints
- `admin.py` - Administrative functions

Each blueprint should:
- Register routes with appropriate prefixes
- Use decorators for common functionality
- Return consistent response formats
- Handle errors gracefully

## Configuration Management

### Configuration Files (config/)

**channels.toml:**
- Define channels with access levels
- Specify channel groups
- Set channel descriptions and display names

**domains.toml:**
- Map domain names to channel access
- Configure themes per domain
- Set domain-specific features (archiving, etc.)

**admin.toml:**
- Configure admin users
- Set admin privileges

**languages.toml:**
- Language support configuration
- Character set definitions

### Environment Variables

- `GOOGLE_CLIENT_ID` - Google OAuth client ID
- `FLASK_ENV` - Flask environment (development/production)
- `TEST_DB_PATH` - Test database path (used by test runner)
- `TESTING` - Set to 'true' during test runs

### Secrets Management

- Store authentication secrets in `~/.atacama_secret`
- Never commit secrets to version control
- Use environment variables for sensitive configuration

## Database

### Schema

Main tables:
- **messages** - Blog posts, articles, messages
- **users** - User accounts and preferences
- **quotes** - Extracted quotes from content
- **user_stats** - Trakaido statistics (per stat type)
- **user_config** - User configuration

### Migrations

Currently using manual schema updates. Consider implementing Alembic for future migrations.

## Testing Strategy

### Test Categories

1. **common** - Core utilities, configuration, logging
2. **web** - Web server, blueprints, routes
3. **aml_parser** - Markup language parsing
4. **react_compiler** - Widget compilation (expensive, requires Node.js)

### Test Structure

- Tests mirror source structure: `src/X/` → `src/tests/X/`
- Use unittest framework
- Test fixtures in `conftest.py`
- Temporary test database per run
- Tests isolated and can run in any order

### Coverage

- Run with `--coverage` flag
- HTML reports generated in `coverage_html/`
- Aim for high coverage on critical paths

## Common Tasks for AI Assistants

### Adding a New Channel

1. Edit `config/channels.toml`
2. Add channel definition with access level and group
3. Optionally add to domain configurations in `config/domains.toml`
4. Restart server to load new configuration

### Creating a New Widget

1. Create React component in appropriate location
2. Use Widget Management UI to compile and test
3. Widget automatically bundled with dependencies
4. Can reference widget in articles using widget tags

### Adding a New Blueprint

1. Create new Python file in `src/atacama/blueprints/` or `src/blog/blueprints/` as appropriate
2. Define blueprint with `Blueprint('name', __name__)`
3. Register routes using decorators
4. Register blueprint in `src/atacama/server.py`
5. Add tests in `src/tests/atacama/` or `src/tests/blog/` as appropriate

### Modifying the Parser

1. Parser located in `src/aml_parser/`
2. Add new markup syntax
3. Update parser logic
4. Add rendering in templates
5. Add tests in `src/tests/aml_parser/`
6. Update README.md with new syntax documentation

### Adding API Endpoints

**For Trakaido:**
1. Add endpoint in `src/trakaido/blueprints/`
2. Use appropriate authentication (nonce-based)
3. Follow existing patterns for response format
4. Add tests in `src/tests/trakaido/`

**For Blog:**
1. Add endpoint in appropriate `src/blog/blueprints/` file
2. Use authentication decorators from `atacama.decorators`
3. Return HTML or JSON as appropriate
4. Add tests in `src/tests/blog/`

## Important Notes for AI Assistants

### When Modifying Code

1. **Always run PRESUBMIT.py** before committing changes
2. **Run relevant tests** to ensure nothing breaks
3. **Update documentation** if adding new features
4. **Check import organization** - follow the convention
5. **Verify third-party imports** are in requirements.txt

### Security Considerations

- Never expose authentication secrets
- Validate user input, especially in parser
- Use parameterized queries (SQLAlchemy handles this)
- Respect channel access controls
- Be cautious with widget compilation (arbitrary code execution)

### Performance Considerations

- React compilation is expensive - cache compiled widgets
- Parser can be intensive for large documents
- Database queries should use appropriate indexes
- Consider pagination for large result sets

### Common Pitfalls

1. **Relative imports** - Don't use them outside tests (PRESUBMIT will catch)
2. **Import path** - Use `from common.base import logger`, not relative paths
3. **Database sessions** - Always properly close sessions
4. **Test isolation** - Tests use temporary database, don't rely on persistent data
5. **Configuration caching** - Configuration is loaded at startup, restart after changes

### Widget Development

- Test widgets thoroughly before deploying
- Use sample widgets as templates
- Be aware of security implications of user-provided code
- Compiled widgets are cached - clear cache if needed
- Widget dependencies must be in supported library list

### Debugging

- Logs written to `logs/` directory (one file per PID)
- Use `src/atacama/blueprints/debug.py` for debug utilities
- Test database separate from production database
- Can run Flask in debug mode for development

## Launch Modes

The `launch.py` script supports multiple modes:

- `--mode web` - Blog server only (default port 5000)
- `--mode spaceship` - Spaceship daemon only (default port 8000)
- `--mode all` - All services (default)
- `--port PORT` - Specify port number

## Production Deployment

See `INSTALL.md` for detailed production setup instructions.

Key points:
- Use systemd services for process management
- Nginx as reverse proxy
- SQLite or PostgreSQL for database
- Proper log rotation
- Security: limited user account, proper file permissions
- Google OAuth configuration for authentication

## Resources

- **README.md** - User-facing documentation
- **INSTALL.md** - Production installation guide
- **config/** - Example configurations
- **src/react_compiler/samples/** - Sample widgets for reference

## Quick Reference

### File Locations

- Configuration: `config/*.toml`
- Models: `src/models/*.py`
- Parser: `src/aml_parser/`
- Blueprints: `src/atacama/blueprints/`, `src/blog/blueprints/`, `src/trakaido/blueprints/`
- Tests: `src/tests/`
- Templates: `src/atacama/templates/`
- Static files: `src/atacama/static/`, `src/atacama/css/`, `src/atacama/js/`

### Key Commands

```bash
python3 launch.py                    # Run all services
python3 run_tests.py                 # Run test suite
python3 PRESUBMIT.py                 # Pre-commit checks
python3 run_react_compiler_tests.py  # React compiler tests
./local_server.sh                    # Development server
```

## Questions or Issues?

When encountering issues:
1. Check logs in `logs/` directory
2. Run PRESUBMIT.py to catch common issues
3. Run relevant tests to verify functionality
4. Check configuration files for correctness
5. Verify dependencies are installed (requirements.txt)

Remember: This is a complex system with three distinct services. Understand which component you're modifying before making changes.
