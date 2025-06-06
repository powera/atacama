
```markdown
# Atacama

A semantic web publishing platform for sharing richly formatted messages, articles, and interactive content.

## Overview

Atacama is a content management system that transforms specially formatted text into visually meaningful web content. It supports multiple content types including messages, articles, and interactive React widgets, all organized into channels with configurable access controls.

## Key Features

### Content Management
- **Multiple Content Types**: Messages, articles, and React widgets
- **Channel System**: Organize content into public, private, or restricted channels
- **Access Control**: Fine-grained permissions with admin capabilities
- **Threading**: Parent/child relationships for message chains

### Rich Text Formatting
- **Semantic Color Blocks**: Apply meaning through color-coded formatting
- **Special Markup**: Support for lists, literal text, wiki links, and more
- **Chinese Annotations**: Automatic pinyin and definition tooltips
- **Chess Notation**: Render chess positions from PGN notation
- **Quote Tracking**: Automatic indexing and collection of quotes

### Widget System
- **React Compiler**: Build and bundle React widgets for browser use
- **Interactive Components**: Create dynamic widgets with full React capabilities
- **Built-in Hooks**: Custom hooks for fullscreen, global settings, and more
- **Dependency Management**: Automatic handling of external libraries
- **Live Preview**: Real-time widget compilation and testing

### User Experience
- **Theme Support**: Light, dark, and high-contrast themes
- **Multi-Domain**: Support for different sites from single installation
- **OAuth Authentication**: Google OAuth integration
- **Preview Mode**: Live preview while composing content

## Formatting System

Atacama uses a custom markup language with semantic color tags:

```
<xantham>🔥 Sarcastic or overconfident tone</xantham>
<red>💡 Forceful, certain statements</red>
<orange>⚔️ Counterpoints and alternative views</orange>
<quote>💬 Quoted material</quote>
<green>⚙️ Technical explanations and code</green>
<teal>🤖 AI/LLM generated content</teal>
<blue>✨ Voice from beyond</blue>
<violet>📣 Serious announcements</violet>
<music>🎵 Musical content</music>
<mogue>🌎 Actions taken</mogue>
<gray>💭 Past stories and memories</gray>
<hazel>🎭 Storytelling and narrative</hazel>
```

### Additional Markup

- `*text*` - Emphasis/italics
- `[[Page Title]]` - Wiki-style links
- `<< literal text >>` - Monospace/code
- `汉字` - Chinese text with annotations
- `https://...` - Auto-linked URLs with YouTube embeds
- `--MORE--` - Content truncation marker
- `----` - Section breaks

### Multi-line blocks

```
<<<
Multiple line content

can span several paragraphs
>>>
```

## React Compiler and Widget System

Atacama includes a powerful React Compiler that allows you to create and host interactive widgets directly within your content. The system provides a complete development environment for React components with automatic bundling and dependency management.

### Widget Development

#### Creating Widgets
Widgets are written as standard React components and can include:
- State management with React hooks
- External library dependencies (Recharts, D3, Lodash, etc.)
- Custom styling and interactions
- API integrations

#### Built-in Hooks
The system provides custom hooks for common widget functionality:
- `useFullscreen` - Manage fullscreen mode for widgets
- `useGlobalSettings` - Access global application settings
- Additional hooks can be added to the `src/react_compiler/js/` directory

#### Sample Widgets
The platform includes several sample widgets demonstrating different capabilities:
- **Basketball.jsx** - Interactive basketball game with fullscreen support
- **Trakaido.jsx** - Lithuanian flashcard application
- **MathQuiz.jsx** - Mathematical quiz component
- **UnitConversion.jsx** - Unit conversion calculator

### Compilation Process

The React Compiler handles the complete build process:

1. **Dependency Detection** - Automatically detects required libraries
2. **Hook Inlining** - Includes built-in hooks directly in the widget code
3. **Webpack Bundling** - Creates browser-ready JavaScript bundles
4. **UMD Export** - Ensures widgets are globally accessible
5. **Minification** - Optimizes code for production use

### Supported Dependencies

Available external libraries include:
- **Recharts** (^2.12.7) - Charts and data visualization
- **Lodash** (^4.17.21) - Utility functions
- **Axios** (^1.6.0) - HTTP client
- **D3** (^7.8.5) - Data visualization
- **Date-fns** (^3.0.0) - Date utilities
- **Lucide React** (^0.263.1) - Icon library

### Widget Hosting

Compiled widgets are:
- Automatically bundled with required dependencies
- Made available as global browser objects
- Integrated into the Atacama rendering system
- Cached for optimal performance

### Testing

The platform includes comprehensive testing for the React Compiler:
- Unit tests for compilation logic
- Integration tests with sample widgets
- Expensive tests requiring Node.js/npm (run separately)

Run React Compiler tests:
```bash
python3 run_react_compiler_tests.py
```

## Architecture

### Backend
- **Framework**: Flask with blueprint architecture
- **Database**: SQLAlchemy with PostgreSQL/SQLite support
- **Parser**: Custom lexer/parser for Atacama markup
- **Authentication**: OAuth 2.0 integration
- **Widget Compiler**: Node.js-based React compilation system

### Frontend
- **JavaScript**: Custom viewer for interactive elements
- **React**: Widget system for dynamic components
- **CSS**: Themeable design with CSS variables

### Configuration
- **Channels**: TOML-based channel configuration
- **Domains**: Multi-domain support with per-domain themes
- **Admin**: Role-based access control system

## Installation

See `INSTALL.md` for detailed setup instructions.

Basic steps:
1. Clone repository
2. Install dependencies: `pip install -r requirements.txt`
3. Install Node.js and npm (required for React Compiler)
4. Configure databases and OAuth
5. Set up channel and domain configurations
6. Run with `launch.py` or `local_server.sh`

### Prerequisites for Widget Development

To use the React Compiler, you'll need:
- **Node.js** (version 14 or higher)
- **npm** (comes with Node.js)

Install on various platforms:
```bash
# macOS
brew install node

# Ubuntu/Debian
sudo apt-get install nodejs npm

# Windows
# Download from https://nodejs.org/
```

## Development

- `run_tests.py` - Run main test suite
- `run_react_compiler_tests.py` - Run React Compiler integration tests
- `PRESUBMIT.py` - Pre-commit checks
- `tools/` - Various development utilities

## Project Structure

```
src/
├── aml_parser/          # Atacama markup parser
│   ├── lexer.py         # Token lexing
│   ├── parser.py        # AST parsing
│   ├── html_generator.py # HTML generation
│   ├── chess.py         # Chess notation support
│   ├── colorblocks.py   # Color block processing
│   └── pinyin.py        # Chinese text annotations
├── common/              # Shared utilities and models
│   ├── base/            # Logging and request handling
│   ├── config/          # Configuration management
│   └── llm/             # LLM integration and widget AI tools
├── models/              # Database models
│   ├── database.py      # Database configuration
│   ├── messages.py      # Message models
│   ├── users.py         # User models
│   ├── quotes.py        # Quote models
│   └── models.py        # Additional models
├── react_compiler/      # React widget compilation system
│   ├── react_compiler.py # Main compiler logic
│   ├── js/              # Built-in hooks
│   │   ├── useFullscreen.js
│   │   └── useGlobalSettings.js
│   └── samples/         # Sample widget demonstrations
│       ├── Basketball.jsx
│       ├── Trakaido.jsx
│       ├── MathQuiz.jsx
│       └── UnitConversion.jsx
├── spaceship/           # Spaceship visualization server
├── tests/               # Test suite
│   ├── aml_parser/      # Parser tests
│   ├── common/          # Common module tests
│   ├── models/          # Database model tests
│   ├── react_compiler/  # React Compiler integration tests
│   └── web/             # Web application tests
├── util/                # Utility scripts
│   ├── importer.py      # Data import utilities
│   ├── export.py        # Data export utilities
│   └── messages.py      # Message utilities
├── web/                 # Flask web application
│   ├── blueprints/      # Modular route handlers
│   │   ├── content.py   # Content viewing
│   │   ├── submit.py    # Content submission
│   │   ├── widgets.py   # Widget management
│   │   ├── react_api.py # React widget API
│   │   └── ...          # Additional blueprints
│   ├── templates/       # Jinja2 templates
│   │   ├── layouts/     # Base templates
│   │   ├── articles/    # Article templates
│   │   ├── widgets/     # Widget templates
│   │   └── ...          # Additional templates
│   ├── css/             # Stylesheets
│   ├── js/              # Client-side JavaScript
│   │   ├── third_party/ # External libraries (React, etc.)
│   │   ├── atacama.js   # Main application JS
│   │   └── diff.js      # Diff utilities
│   ├── react/           # React build system
│   ├── static/          # Static assets
│   └── decorators/      # Request decorators
└── constants.py         # Application constants
```

## Current Status

Atacama is in active development with the following components operational:

- Core message/article publishing system
- Channel-based access control
- Rich text formatting with custom parser
- User authentication and preferences
- Admin interface for user management
- **React widget system with compilation and hosting**
- **Built-in hooks and dependency management**
- **Widget AI tools for improvement and generation**
- Multi-theme support
- Domain configuration for multi-site hosting

## License

[License information to be added]

## Contributing

[Contributing guidelines to be added]

### Widget Development

When contributing widgets:
1. Add `.jsx` files to `src/react_compiler/samples/`
2. Follow React best practices and use built-in hooks when possible
3. Test compilation with `run_react_compiler_tests.py`
4. Document any special dependencies or requirements
5. Ensure widgets export the expected component name
```
