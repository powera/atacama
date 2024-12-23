# Installation Guide

This guide covers setting up Atacama Message Processor in a production environment.

## Prerequisites

- Python 3.9 or higher
- Nginx
- SQLite3
- Systemd (for service management)
- Git

## System Setup

1. Create dedicated user account:
```bash
sudo useradd -m -s /bin/bash atacama
# Configure limited sudo access for service management
echo "atacama ALL=(root) NOPASSWD: /bin/systemctl * atacama-web" | sudo tee /etc/sudoers.d/atacama
```

2. Clone repository:
```bash
sudo -u atacama git clone https://github.com/yourdomain/atacama.git /home/atacama/atacama
cd /home/atacama/atacama
```

3. Set up Python virtual environment:
```bash
sudo -u atacama python3 -m venv /home/atacama/venv
source /home/atacama/venv/bin/activate
pip install -r requirements.txt
```

## Configuration

### Authentication Setup

1. Create authentication secret:
```bash
echo "your-secure-passcode" > /home/atacama/.atacama_secret
chmod 600 /home/atacama/.atacama_secret
```

2. (Optional) Configure Google OAuth:
- Create project in Google Cloud Console
- Enable OAuth2 API
- Create OAuth2 credentials
- Add authorized redirect URIs
- Set environment variable: `export GOOGLE_CLIENT_ID="your-client-id"`

### Email Integration (Optional)

Create `/home/atacama/email_config.json`:
```json
{
    "host": "your.imap.server",
    "port": 143,
    "username": "your_username",
    "password": "your_password",
    "fetch_interval": 300
}
```

## Database Setup

The system uses SQLite and will automatically create its database on first run. By default, it's stored at `/home/atacama/atacama/emails.db`.

For production, ensure proper permissions:
```bash
touch /home/atacama/atacama/emails.db
chown atacama:atacama /home/atacama/atacama/emails.db
chmod 600 /home/atacama/atacama/emails.db
```

## Service Configuration

### Web Server Service

Create `/etc/systemd/system/atacama-web.service`:
```ini
[Unit]
Description=Atacama Message Processor Web Server
After=network.target

[Service]
Type=simple
User=atacama
Group=atacama
WorkingDirectory=/home/atacama/atacama
Environment=FLASK_ENV=production
Environment=GOOGLE_CLIENT_ID=your-client-id
ExecStart=/home/atacama/venv/bin/python launch.py --mode web --port 5000
Restart=always

[Install]
WantedBy=multi-user.target
```

### Email Processor Service

Create `/etc/systemd/system/atacama-mail.service`:
```ini
[Unit]
Description=Atacama Message Processor Mail Service
After=network.target

[Service]
Type=simple
User=atacama
Group=atacama
WorkingDirectory=/home/atacama/atacama
Environment=FLASK_ENV=production
ExecStart=/home/atacama/venv/bin/python launch.py --mode mail
Restart=always

[Install]
WantedBy=multi-user.target
```

### Enable Services

```bash
sudo systemctl daemon-reload
sudo systemctl enable atacama-web
sudo systemctl enable atacama-mail  # If using email processing
sudo systemctl start atacama-web
sudo systemctl start atacama-mail   # If using email processing
```

## Nginx Configuration

Create `/etc/nginx/sites-available/atacama`:
```nginx
server {
    listen 80;
    server_name your.domain.com;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /css/ {
        alias /home/atacama/atacama/web/css/;
    }
}
```

Enable the site:
```bash
sudo ln -s /etc/nginx/sites-available/atacama /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

## Logging Configuration

Logs are written to `/home/atacama/atacama.log`. Ensure proper permissions:
```bash
touch /home/atacama/atacama.log
chown atacama:atacama /home/atacama/atacama.log
```

## Testing Installation

1. Check service status:
```bash
sudo systemctl status atacama-web
sudo systemctl status atacama-mail  # If using email processing
```

2. Verify web access:
```bash
curl http://localhost:5000/
```

3. Monitor logs:
```bash
tail -f /home/atacama/atacama.log
```

## Troubleshooting

### Common Issues

1. Permission errors:
- Check file ownership: `ls -l /home/atacama/atacama.log`
- Check directory permissions: `ls -ld /home/atacama/atacama`

2. Service won't start:
- Check logs: `journalctl -u atacama-web`
- Verify Python path: `systemctl show atacama-web | grep ExecStart`

3. Web access fails:
- Check Nginx error log: `tail /var/log/nginx/error.log`
- Verify port availability: `netstat -tlpn | grep 5000`

### Getting Help

For more assistance:
1. Check the application logs
2. Review Nginx and systemd logs
3. Contact the development team
