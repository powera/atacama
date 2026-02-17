"""Base functionality for Atacama - logging and request handling."""

# Logging configuration
from .logging_config import configure_logging, get_logger

# Request logging
from .request_logger import RequestLogger, get_request_logger

__all__ = [
    # Logging config
    "configure_logging",
    "get_logger",
    # Request logging
    "RequestLogger",
    "get_request_logger",
]
