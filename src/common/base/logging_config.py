"""
Centralized logging configuration for the Atacama application.

This module sets up consistent logging across the entire application with features like:
- Detailed formatting including line numbers and function names
- Both console and file output
- Automatic log rotation
- Different logging levels for different parts of the application
- Support for PID and timestamp in log filenames for better tracking
"""

import logging
import logging.handlers
import os
from pathlib import Path
from typing import Optional

import constants

def configure_logging(
    log_level: str = "INFO",
    app_log_level: str = "DEBUG",
    log_filename: Optional[str] = None
) -> None:
    """
    Configure application-wide logging settings.
    
    This function sets up a comprehensive logging configuration that includes:
    - Console output for immediate feedback
    - Rotating file logs for persistent records
    - Detailed formatting with line numbers and function names
    - Optional custom log filename with PID and timestamp
    
    Args:
        log_level: Root logger level (default: "INFO")
        app_log_level: Application-specific logger level (default: "DEBUG")
        log_filename: Optional custom log filename to use instead of default
    """
    # Create a detailed formatter that helps with debugging
    formatter = logging.Formatter(
        fmt='%(asctime)s - %(levelname)s - %(name)s - %(filename)s:%(lineno)d:%(funcName)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Configure the root logger first
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))
    
    # Clear any existing handlers to avoid duplicates on reconfiguration
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Add console output handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # Set up file logging if enabled
    log_dir = Path(constants.LOG_DIR)
        
    # Create log directory if it doesn't exist
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Determine the log filename
    if log_filename:
        log_file_path = log_dir / log_filename
    else:
        log_file_path = log_dir / 'atacama.log'
    
    # Create rotating file handler
    file_handler = logging.handlers.RotatingFileHandler(
        log_file_path,
        maxBytes=1024 * 1024,  # 1MB per file
        backupCount=10,        # Keep 10 backup files
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)
    
    # Configure application-specific logger with more detailed output
    app_logger = logging.getLogger('web')
    app_logger.setLevel(getattr(logging, app_log_level.upper()))
    
    # Log the initialization
    logging.info(f"Logging initialized: root_level={log_level}, app_level={app_log_level}, log_file={log_file_path}")

def get_logger(name: str) -> logging.Logger:
    """
    Get a logger with the standardized configuration.
    
    This is a convenience function to ensure consistent logger naming
    and configuration across the application.
    
    Args:
        name: Name for the logger, typically __name__ from the calling module
        
    Returns:
        A configured logger instance
    """
    return logging.getLogger(name)