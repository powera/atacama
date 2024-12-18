# Atacama Mail Server

A secure SMTP server implementation that integrates with the Atacama email processing system. This server provides user authentication, TLS encryption, and seamless processing of emails using Atacama's color-coding system.

## Features

- TLS-encrypted SMTP server (port 587)
- User authentication with bcrypt password hashing
- SQLAlchemy integration for user management
- Automatic email processing using Atacama's color scheme
- Session management and connection pooling
- Systemd service integration

## Prerequisites

- Python 3.8+
- SQLAlchemy
- bcrypt
- aiosmtpd
- SSL certificate and private key
- Existing Atacama installation

## Installation

1. Set up the mail server user:
```bash
sudo useradd -r -s /bin/false atacama-mail
```

2. Create required directories:
```bash
sudo mkdir -p /etc/atacama/mail
sudo chown -R atacama-mail:atacama-mail /etc/atacama/mail
```

3. Generate SSL certificates:
```bash
sudo openssl req -x509 -newkey rsa:4096 \
    -keyout /etc/atacama/mail/key.pem \
    -out /etc/atacama/mail/cert.pem \
    -days 365 -nodes
```

4. Install Python dependencies:
```bash
pip install aiosmtpd bcrypt sqlalchemy
```

5. Set up the systemd service:
```bash
sudo cp atacama-mail.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable atacama-mail
sudo systemctl start atacama-mail
```

## Configuration

The mail server uses SQLAlchemy for user management. Create users through the SQLAlchemy session:

```python
from mail_server import MailUser

# Create a new session
session = Session()

# Add a new user
new_user = MailUser(
    username="user@earlyversion.com",
    password_hash=MailUser.hash_password("secure_password")
)
session.add(new_user)
session.commit()
```

## Security Considerations

- Always use strong passwords
- Regularly rotate SSL certificates
- Keep system and Python packages updated
- Monitor authentication logs
- Implement rate limiting if needed
- Set appropriate file permissions for SSL certificates

## Monitoring

The server logs to the system journal. View logs with:
```bash
journalctl -u atacama-mail
```

## Integration with Atacama

The mail server automatically processes incoming emails using Atacama's color scheme processor. Each email is:

1. Authenticated against the user database
2. Processed for color tags
3. Stored in the Atacama database
4. Available through the existing Atacama API

## Development

To run the server in development mode:
```bash
python mail_server.py
```

The server will start on port 587 by default. For development, you may want to use port 2587 to avoid requiring root privileges.
