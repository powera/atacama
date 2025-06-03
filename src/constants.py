import os
from pathlib import Path
from typing import Optional

# System state
TESTING: bool = False 
INITIALIZED: bool = False

# Get the src directory
SRC_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SRC_DIR)

# Define common paths relative to project root
WEB_DIR = os.path.join(SRC_DIR, "web")
STATIC_DIR = os.path.join(WEB_DIR, "static")

KEY_DIR = os.path.join(PROJECT_ROOT, "keys")
LOG_DIR = os.path.join(PROJECT_ROOT, "logs")
REQUEST_LOG_DIR = os.path.join(LOG_DIR, "requests")
CONFIG_DIR = os.path.join(PROJECT_ROOT, "config")
DATA_DIR = os.path.join(PROJECT_ROOT, "data")

REACT_COMPILER_JS_DIR = os.path.join(SRC_DIR, 'react_compiler', "js")

LITHUANIAN_AUDIO_DIR = '/home/atacama/trakaido/'

# Database path - will be updated when testing mode is set
_PROD_DB_PATH = os.path.join(PROJECT_ROOT, "emails.db")
_TEST_DB_PATH: str = "sqlite:///:memory:"
DB_PATH = _PROD_DB_PATH

def init_testing(test_db_path: Optional[str] = None) -> None:
    """
    Initialize system for testing mode.
    
    :param test_db_path: Optional explicit test database path, defaults to in-memory SQLite
    """
    global TESTING, INITIALIZED, DB_PATH, _TEST_DB_PATH
    TESTING = True
    INITIALIZED = True
    if test_db_path:
        _TEST_DB_PATH = test_db_path
    DB_PATH = _TEST_DB_PATH

def init_production() -> None:
    """Initialize system for production mode."""
    global TESTING, INITIALIZED, DB_PATH
    TESTING = False
    INITIALIZED = True
    DB_PATH = _PROD_DB_PATH

def reset() -> None:
    """Reset to uninitialized state (primarily for testing)."""
    global TESTING, INITIALIZED, DB_PATH, _TEST_DB_PATH
    TESTING = False
    INITIALIZED = False
    DB_PATH = _PROD_DB_PATH
    _TEST_DB_PATH = None

def is_development_mode() -> bool:
    """
    Check if the application is running in development mode.
    
    :return: True if FLASK_ENV is set to 'development', False otherwise
    """
    flask_env = os.getenv('FLASK_ENV', 'production').lower()
    return flask_env == 'development'
