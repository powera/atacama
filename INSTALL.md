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


### Enable Services

```bash
sudo systemctl daemon-reload
sudo systemctl enable atacama-web
sudo systemctl start atacama-web
```

## Nginx Configuration

Create `/etc/nginx/sites-available/atacama` based on `src/web/nginx.conf`.

Enable the site:
```bash
sudo ln -s /etc/nginx/sites-available/atacama /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

## Logging Configuration

Logs are written to `/home/atacama/atacama/logs/`, to a unique file per PID. Ensure proper permissions:
```bash
mkdir /home/atacama/atacama/logs/
chown atacama:atacama /home/atacama/atacama/logs/
```

## Testing Installation

1. Check service status:
```bash
sudo systemctl status atacama-web
```

2. Verify web access:
```bash
curl http://localhost:5000/
```

3. Monitor logs.

## Troubleshooting

### Common Issues

1. Service won't start:
- Check logs: `journalctl -u atacama-web`
- Verify Python path: `systemctl show atacama-web | grep ExecStart`

2. Web access fails:
- Check Nginx error log: `tail /var/log/nginx/error.log`
- Verify port availability: `netstat -tlpn | grep 5000`