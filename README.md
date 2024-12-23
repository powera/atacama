# Atacama Message Processor

Atacama is a message processing system that applies custom color-based formatting to text based on semantic meaning. It processes messages containing special color tags and converts them into HTML with appropriate styling.

## Features

- **Color Tag Processing**: Converts semantic color tags to styled HTML/CSS
- **Web Interface**: Submit and view messages through a clean web UI
- **REST API**: Process messages programmatically via HTTP endpoints
- **Message Threading**: Support for message chains and parent/child relationships
- **Chinese Annotations**: Hover-based annotations for Chinese characters
- **Quote Extraction**: Automatic extraction and indexing of quotes and aphorisms
- **LLM Annotations**: Support for large language model output annotation
- **Email Integration**: Optional IMAP-based email processing daemon

## Color Tags

Messages can include the following semantic color tags:

- `<xantham>` - Sarcastic or overconfident content
- `<red>` - Forceful statements and informed opinions  
- `<orange>` - Counterpoints and alternate views
- `<yellow>` - Quotes and referenced content
- `<green>` - Technical explanations and commentary
- `<teal>` - LLM/AI generated content
- `<blue>` - Voice from beyond
- `<violet>` - Serious content
- `<mogue>` - Actions taken and changes made
- `<gray>` - Past stories and historical context

## Usage

### Web Interface

The main web interface provides:
- Message submission form with color tag preview
- Recent message listing and threading view
- Individual message view with formatting
- Print-optimized message display
- Optional authentication for message submission

### API Endpoints

#### Process Message
```http
POST /process
Content-Type: application/json

{
    "subject": "Message Subject",
    "content": "Content with <red>color tags</red>",
    "parent_id": 123  # Optional, for message threading
}
```

#### Retrieve Message
```http
GET /messages/<message_id>
Accept: text/html  # Optional, for HTML formatted version
```

#### Submit via Form
```http
GET/POST /submit
```

## Development Status

The project is currently in pre-release testing at earlyversion.com. It consists of several components:

- Web server (port 5000)
- Email processor (separate service)
- Systemd service configurations
- Nginx reverse proxy setup

Each server instance runs under its own user account with appropriate service isolation.

## Logging

All components log to `atacama.log` with configurable log levels:
- Server events and message processing
- Database operations
- Email fetching status (when enabled)
- Authentication events

## Security

- Google OAuth2 integration for authenticated endpoints
- Development authentication fallback available
- HTML sanitization for message content
- Rate limiting on API endpoints
