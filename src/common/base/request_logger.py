from datetime import datetime
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from typing import Optional, Dict, Any

from flask import request, session, g

import constants

class RequestLogger:
    # Sensitive parameters that should never be logged
    SENSITIVE_PARAMS = {'credential', 'token', 'password', 'secret', 'auth', 'key'}
    
    def __init__(self, app=None):
        self.log_dir = constants.REQUEST_LOG_DIR
        self.trusted_proxies = ['127.0.0.1', '::1']
        if app:
            self.init_app(app)

    def init_app(self, app):
        # Ensure log directory exists
        os.makedirs(self.log_dir, exist_ok=True)

        # Create request logger with separate handlers for different levels
        request_logger = logging.getLogger('request_logger')
        request_logger.propagate = False
        request_logger.setLevel(logging.DEBUG)

        # Handler for detailed DEBUG logs
        debug_handler = RotatingFileHandler(
            os.path.join(self.log_dir, 'requests.debug.log'),
            maxBytes=10000000,  # 10MB
            backupCount=10
        )
        debug_handler.setLevel(logging.DEBUG)
        debug_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s'
        )
        debug_handler.setFormatter(debug_formatter)
        debug_handler.addFilter(lambda record: record.levelno == logging.DEBUG)
        request_logger.addHandler(debug_handler)

        # Handler for basic INFO logs
        info_handler = RotatingFileHandler(
            os.path.join(self.log_dir, 'requests.log'),
            maxBytes=10000000,  # 10MB
            backupCount=10
        )
        info_handler.setLevel(logging.INFO)
        info_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s'
        )
        info_handler.setFormatter(info_formatter)
        info_handler.addFilter(lambda record: record.levelno >= logging.INFO)
        request_logger.addHandler(info_handler)

        # Add console handler if environment variable is set (for development)
        if os.getenv('ATACAMA_REQUEST_LOG_CONSOLE'):
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.DEBUG)
            console_formatter = logging.Formatter(
                'REQUEST: %(asctime)s - %(levelname)s - %(message)s'
            )
            console_handler.setFormatter(console_formatter)
            request_logger.addHandler(console_handler)

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
            real_ip = request.headers.get('X-Real-IP')
            if real_ip and request.remote_addr in self.trusted_proxies:
                ip_address = real_ip
            else:
                ip_address = request.remote_addr

            # Basic log entry for INFO level
            info_entry = {
                'timestamp': datetime.utcnow().isoformat(),
                'method': request.method,
                'path': request.path,
                'status_code': response.status_code,
                'duration_ms': int(duration.total_seconds() * 1000),
            }
            
            # Log basic info at INFO level
            request_logger.info(json.dumps(info_entry))

            # Detailed log entry for DEBUG level
            debug_entry = info_entry.copy()
            debug_entry.update({
                'user_email': user_email,
                'ip_address': ip_address,
                'user_agent': request.user_agent.string,
                'referer': request.referrer,
                'response_size': response.content_length or len(response.get_data()),
            })

            # Add sanitized query parameters
            if request.args:
                sanitized_params = {
                    k: v for k, v in request.args.items() 
                    if k.lower() not in self.SENSITIVE_PARAMS
                }
                if sanitized_params:
                    debug_entry['query_params'] = sanitized_params

            # Add sanitized request body for POST/PUT requests
            if request.method in ['POST', 'PUT'] and request.is_json:
                body = request.get_json(silent=True)  # Won't raise exception
                if body and isinstance(body, dict):
                    sanitized_body = {
                        k: v for k, v in body.items()
                        if k.lower() not in self.SENSITIVE_PARAMS
                    }
                    if sanitized_body:
                        # Convert to JSON string and limit to 480 bytes
                        body_json = json.dumps(sanitized_body)
                        if len(body_json.encode('utf-8')) > 480:
                            # Truncate and add indicator
                            truncated_body = body_json.encode('utf-8')[:480].decode('utf-8', errors='ignore')
                            debug_entry['request_body'] = truncated_body + "...[TRUNCATED]"
                        else:
                            debug_entry['request_body'] = body_json

            # Log detailed info at DEBUG level
            request_logger.debug(json.dumps(debug_entry))

            return response

        # Register error handler
        @app.errorhandler(Exception)
        def log_exception(error):
            request_logger.error(f"Unhandled exception: {str(error)}", exc_info=True)
            raise error

def get_request_logger(name: str = 'request_logger') -> logging.Logger:
    """Helper function to get the request logger instance."""
    return logging.getLogger(name)
