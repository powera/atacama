# AGENTS.md - AI Assistant Guide for Atacama

Atacama is a multi-purpose web application with three main services:

1. **Blog Server (Atacama CMS)** - Semantic web publishing with custom markup, React widgets, and multi-domain support
2. **Trakaido Stats API** - Backend for Lithuanian language learning statistics and flashcard progress
3. **Spaceship Daemon** - Lightweight proof-of-life server serving XPlanet Earth images

See `.agents/peer-repo/` for summaries of related repositories (Trakaido app, Greenland linguistic database).

## Before Submitting

```bash
black .                              # Format Python code (required)
python3 PRESUBMIT.py                 # Import checks (required)
python3 run_tests.py                 # Run test suite
```

## Quick Reference

```bash
python3 launch.py                    # Run all services
python3 launch.py --mode web         # Blog server only (port 5000)
python3 launch.py --mode spaceship   # Spaceship only (port 8000)
./local_server.sh                    # Development server convenience script
python3 run_tests.py --category web  # Run specific test category
```

## Project Structure

```
atacama/
├── config/                    # TOML config files
│   ├── channels.toml          # Channel definitions and access levels
│   ├── domains.toml           # Multi-domain config and themes
│   ├── admin.toml             # Admin user config
│   └── languages.toml         # Language support
├── src/
│   ├── aml_parser/            # Atacama Markup Language parser
│   │   ├── lexer.py           # Tokenizer
│   │   ├── parser.py          # Parser
│   │   ├── html_generator.py  # HTML rendering
│   │   ├── chess.py           # Chess notation rendering
│   │   ├── colorblocks.py     # Color tag handling
│   │   ├── english_annotations.py
│   │   └── pinyin.py          # Chinese pinyin annotations
│   ├── common/                # Shared utilities
│   │   ├── atomic_file.py
│   │   ├── base/              # Logging and request handling
│   │   ├── config/            # Config management (channels, domains, languages)
│   │   ├── llm/               # LLM integration (widget generation, editor assist)
│   │   └── services/          # Shared services (archive, etc.)
│   ├── models/                # SQLAlchemy database models
│   │   ├── database.py        # DB initialization
│   │   ├── messages.py        # Content models
│   │   ├── users.py           # User models
│   │   ├── quotes.py          # Quote tracking
│   │   ├── classrooms.py      # Classroom models
│   │   └── models.py          # Additional models
│   ├── react_compiler/        # React widget compilation (Webpack/UMD)
│   │   ├── react_compiler.py  # Main compiler
│   │   ├── lib.py             # Library functions
│   │   ├── js/                # Built-in hooks (useFullscreen, useGlobalSettings)
│   │   └── samples/           # Sample widgets (Basketball, Trakaido, MathQuiz)
│   ├── spaceship/             # XPlanet image server
│   │   └── server.py
│   ├── atacama/               # Core Flask app
│   │   ├── server.py          # Main application entry point
│   │   ├── blueprints/        # auth, debug, errors, metrics, nav, static
│   │   ├── decorators/        # auth, navigation decorators
│   │   ├── templates/         # Jinja2 templates
│   │   ├── css/               # Stylesheets
│   │   ├── js/                # Client JS (atacama.js, lithuanianApi.js)
│   │   └── static/            # Static assets
│   ├── blog/                  # Blog/CMS module
│   │   └── blueprints/        # admin, article, content, editor, feeds, quotes,
│   │                          #   shared, statistics, submit, widgets
│   ├── trakaido/              # Trakaido Stats API
│   │   ├── models.py          # Trakaido-specific models
│   │   └── blueprints/        # classroom_stats, grammarstats, nonce_utils,
│   │                          #   shared, stats_backend, stats_metrics,
│   │                          #   stats_schema, stats_snapshots, stats_sqlite,
│   │                          #   trakaido_tools, userconfig_v2, userstats
│   ├── tests/                 # Test suite (mirrors src structure)
│   │   ├── conftest.py
│   │   ├── common/            # config, atomic_file, archive_service tests
│   │   ├── atacama/           # auth, error handler, metrics tests
│   │   ├── blog/              # content serving, submit, template tests
│   │   ├── aml_parser/        # chess, lexer, parser tests
│   │   ├── react_compiler/    # sample compilation tests
│   │   └── trakaido/          # stats, nonce, userconfig, classroom tests
│   ├── util/                  # Utility scripts (db, export, import, etc.)
│   └── constants.py           # Application-wide constants
├── launch.py                  # Multi-mode launcher
├── local_server.sh            # Dev server script
├── requirements.txt           # Python dependencies
├── run_tests.py               # Test runner
├── run_react_compiler_tests.py
├── PRESUBMIT.py               # Pre-commit validation
└── INSTALL.md                 # Production setup guide
```

## Key Components

### Atacama Markup Language (AML)

Custom semantic markup using color-coded tags:

| Tag | Meaning |
|-----|---------|
| `<xantham>` | Sarcastic/overconfident |
| `<red>` | Forceful |
| `<orange>` | Counterpoint |
| `<quote>` | Quoted material |
| `<green>` | Technical |
| `<teal>` | AI-generated |
| `<blue>` | Voice from beyond |
| `<violet>` | Serious announcement |
| `<music>` | Musical content |
| `<mogue>` | Actions taken |
| `<gray>` | Past stories |
| `<hazel>` | Storytelling |

Other syntax: `*emphasis*`, `[[Wiki Links]]`, `<< monospace >>`, multi-line blocks with `<<<`/`>>>`, automatic Chinese pinyin, chess notation, YouTube embedding.

### React Widget System

Compiles React 19 components (Webpack → UMD bundles). Supported libraries: Recharts, Lodash, Axios, D3, Date-fns, Lucide React. See `src/react_compiler/samples/` for examples.

### Channel System

Three access levels: `public`, `private` (auth required), `restricted` (admin only). Configured in `config/channels.toml`. Multiple channel groups: Recreation, Media, Civics, Religion, Technology, Atacama, Personal, General.

### Trakaido Stats API

Nonce-based auth, cross-domain cookie sharing (`*.trakaido.com`). Tracks vocabulary, flashcards, grammar stats with historical snapshots. Also supports classroom stats.

## Code Conventions

**Imports:** stdlib → third-party → local, alphabetically sorted within each group. No relative imports outside test files. All third-party imports must be in `requirements.txt`. PRESUBMIT.py enforces this.

**Style:** PEP 8, `black`-formatted. Snake_case file names. Test files: `test_*.py`.

**Database:** SQLAlchemy ORM; use `src/models/database.py` for initialization. Sessions must be properly closed. Support both PostgreSQL and SQLite.

**Blueprints:** Register with appropriate prefixes; use decorators for auth/navigation; register in `src/atacama/server.py`.

## Configuration

- `config/channels.toml` - Channels and access levels
- `config/domains.toml` - Domain-to-channel mapping, themes
- `config/admin.toml` - Admin users
- `config/languages.toml` - Language support

**Environment variables:** `GOOGLE_CLIENT_ID`, `FLASK_ENV`, `TEST_DB_PATH`, `TESTING`

**Secrets:** `~/.atacama_secret` (never commit)

## Database Schema

Main tables: `messages`, `users`, `quotes`, `classrooms` (blog); `user_stats`, `user_config` (trakaido).

## Testing

```bash
python3 run_tests.py                       # All tests
python3 run_tests.py --category common     # Specific category
python3 run_tests.py --category web
python3 run_tests.py --category aml_parser
python3 run_tests.py --coverage            # With HTML coverage report
python3 run_tests.py --fail-fast
python3 run_react_compiler_tests.py        # React compiler (requires Node.js)
```

Tests use a temporary database per run; do not rely on persistent data.

## Common Pitfalls

- **Relative imports** outside tests → PRESUBMIT will catch; use `from common.base import logger`
- **DB sessions** → always close properly
- **Config changes** require server restart (loaded at startup)
- **Widget compilation** is expensive → compiled widgets are cached
- **Widget dependencies** must be in the supported library list

## Logs

Written to `logs/` (one file per PID). Debug utilities in `src/atacama/blueprints/debug.py`.
