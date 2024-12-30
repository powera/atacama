from flask import request, session, g
from datetime import datetime
import logging
import json
from typing import Optional, Dict, Any
from logging.handlers import RotatingFileHandler
import os
from functools import wraps

class RequestLogger:
    def __init__(self, app=None, log_dir: str = "logs"):
        self.log_dir = log_dir
        self.trusted_proxies = ['127.0.0.1', '::1']
        if app:
            self.init_app(app)

    def init_app(self, app):
        # Ensure log directory exists
        os.makedirs(self.log_dir, exist_ok=True)

        # Create request logger
        request_logger = logging.getLogger('request_logger')
        request_logger.setLevel(logging.INFO)

        # Create rotating file handler
        handler = RotatingFileHandler(
            os.path.join(self.log_dir, 'requests.log'),
            maxBytes=10000000,  # 10MB
            backupCount=10
        )
        
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        request_logger.addHandler(handler)

        # Register before_request handler
        @app.before_request
        def before_request():
            g.request_start_time = datetime.utcnow()

        # Register after_request handler
        @app.after_request
        def after_request(response):
            if request.path.startswith('/static/'):
                return response

            # Calculate request duration
            duration = datetime.utcnow() - g.request_start_time

            # Get user information from session
            user_info = session.get('user', {})
            user_email = user_info.get('email', 'anonymous')

            # Get IP address from NGINX
            forwarded_for = request.headers.get('X-Forwarded-For')
            print(forwarded_for)
            print(request.headers.get('X-Real-IP'))
            if forwarded_for and request.remote_addr in self.trusted_proxies:
                ip_address = forwarded_for.split(',')[0].strip()
            else:
                ip_address = request.remote_addr

            # Build log entry
            log_entry = {
                'timestamp': datetime.utcnow().isoformat(),
                'method': request.method,
                'path': request.path,
                'status_code': response.status_code,
                'duration_ms': int(duration.total_seconds() * 1000),
                'user_email': user_email,
                'ip_address': ip_address,
                'user_agent': request.user_agent.string,
                'referer': request.referrer,
                'query_params': dict(request.args),
            }

            # Add request body for POST/PUT requests (excluding file uploads and sensitive data)
            if request.method in ['POST', 'PUT'] and request.is_json:
                body = request.get_json()
                if isinstance(body, dict):
                    # Remove sensitive fields
                    sanitized_body = {k: v for k, v in body.items() 
                                   if k.lower() not in ['password', 'token', 'credential']}
                    log_entry['request_body'] = sanitized_body

            # Log the entry
            request_logger.info(json.dumps(log_entry))

            return response

        # Register error handler
        @app.errorhandler(Exception)
        def log_exception(error):
            request_logger.error(f"Unhandled exception: {str(error)}", exc_info=True)
            raise error

def get_request_logger(name: str = 'request_logger') -> logging.Logger:
    """Helper function to get the request logger instance."""
    return logging.getLogger(name)
