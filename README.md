# Atacama Email Processor

Atacama is an email processing system that applies custom color-based formatting to emails based on semantic meaning. It processes emails containing special color tags and converts them into HTML with appropriate styling.

## Features

- Processes emails with custom color tags representing different semantic meanings
- Converts color tags to HTML/CSS styling
- Stores original and processed emails in SQLite database
- Provides REST API endpoints for email processing
- Includes automatic email fetching daemon for IMAP servers
- Special handling for different content types (e.g., Comic Sans for LLM outputs)

## Color Scheme

The system recognizes the following color tags and their semantic meanings:

- `<xantham>` (infrared) - Sarcastic or overconfident content
- `<red>` - Forceful statements and informed opinions
- `<orange>` - Counterpoints (often starting with "well, actually")
- `<yellow>` - Direct quotes and snowclones
- `<green>` - Technical explanations and meta-commentary
- `<teal>` - LLM model outputs (rendered in Comic Sans)
- `<blue>` - Voice from beyond
- `<violet>` - Serious content
- `<mogue>` (ultraviolet) - Descriptions of actions taken
- `<gray>` - Past stories and historical quotes

## Setup

1. Install dependencies:
```bash
pip install flask sqlalchemy waitress
```

2. Configure email settings (optional):
Create `email_config.json`:
```json
{
    "host": "your.imap.server",
    "port": 143,
    "username": "your_username",
    "password": "your_password",
    "fetch_interval": 300
}
```

3. Initialize the database:
The system will automatically create an SQLite database (`emails.db`) on first run.

## Usage

### Running the Server

```bash
python server.py
```

This will start:
- The Flask web server on port 5000
- The email fetcher daemon (if configured)

### API Endpoints

#### Process Email
```http
POST /process
Content-Type: application/json

{
    "subject": "Email Subject",
    "content": "Email content with <red>color tags</red>"
}
```

#### Retrieve Email
```http
GET /emails/<email_id>
```

### Example Usage

```python
import requests

email_content = """
<red>Important notice:</red>
<green>This is a technical explanation.</green>
<teal>This is AI-generated content.</teal>
"""

response = requests.post('http://localhost:5000/process', 
    json={
        'subject': 'Test Email',
        'content': email_content
    }
)

processed_email = response.json()
```

## Database Schema

The system uses SQLAlchemy with the following schema:

- `emails`
  - `id`: Integer (Primary Key)
  - `subject`: String(255)
  - `content`: Text (Original content)
  - `processed_content`: Text (HTML/CSS formatted content)
  - `created_at`: DateTime

## Logging

Logs are written to `email_processor.log` and include:
- Server start/stop events
- Email processing status
- Error messages
- IMAP connection status (if enabled)

## Error Handling

The system includes comprehensive error handling for:
- Invalid email formats
- Database connection issues
- IMAP connection failures
- Missing or malformed color tags

## Security Notes

- Ensure proper access controls for the API endpoints
- Store email credentials securely
- Review processed content for potentially harmful HTML/CSS

## Contributing

When contributing to this project:
1. Follow the existing code style
2. Add tests for new features
3. Update documentation as needed
4. Ensure all tests pass before submitting changes
