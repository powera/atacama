import os
from pathlib import Path
from typing import Optional

# System state
TESTING: bool = False 
INITIALIZED: bool = False
SERVICE: Optional[str] = None  # Track current service (trakaido, blog, spaceship)

def is_development_mode() -> bool:
    """
    Check if the application is running in development mode.
    
    :return: True if FLASK_ENV is set to 'development', False otherwise
    """
    flask_env = os.getenv('FLASK_ENV', 'production').lower()
    return flask_env == 'development'

# Get the src directory
SRC_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SRC_DIR)

# Define common paths relative to project root
WEB_DIR = os.path.join(SRC_DIR, "atacama")
STATIC_DIR = os.path.join(WEB_DIR, "static")

KEY_DIR = os.path.join(PROJECT_ROOT, "keys")

def get_log_dir() -> str:
    """
    Get the log directory path, optionally with service subdirectory.
    
    :return: Path to the log directory
    """
    base_log_dir = os.path.join(PROJECT_ROOT, "logs")
    
    # If a service is specified and it's trakaido or blog, create a subdirectory
    if SERVICE in ['trakaido', 'blog']:
        return os.path.join(base_log_dir, SERVICE)
    
    return base_log_dir

# Dynamic log directory based on service
LOG_DIR = get_log_dir()
REQUEST_LOG_DIR = os.path.join(LOG_DIR, "requests")
CONFIG_DIR = os.path.join(PROJECT_ROOT, "config")
DATA_DIR = os.path.join(PROJECT_ROOT, "data")

REACT_COMPILER_JS_DIR = os.path.join(SRC_DIR, 'react_compiler', "js")

# Audio directories
_PROD_TRAKAIDO_AUDIO_BASE_DIR = '/home/atacama/trakaido/'
_DEV_TRAKAIDO_AUDIO_BASE_DIR = '/Users/powera/repo/trakaido/audio/'

def get_trakaido_audio_base_dir() -> str:
    """
    Get the base Trakaido audio directory for all languages.

    :return: Path to the base audio directory
    """
    if is_development_mode():
        return _DEV_TRAKAIDO_AUDIO_BASE_DIR
    return _PROD_TRAKAIDO_AUDIO_BASE_DIR

# Database path - will be updated when testing mode is set
_PROD_DB_PATH = os.path.join(PROJECT_ROOT, "emails.db")
_TEST_DB_PATH: str = "sqlite:///:memory:"
DB_PATH = _PROD_DB_PATH

def init_testing(test_db_path: Optional[str] = None, service: Optional[str] = None) -> None:
    """
    Initialize system for testing mode.
    
    :param test_db_path: Optional explicit test database path, defaults to in-memory SQLite
    :param service: Optional service name (trakaido, blog, spaceship)
    """
    global TESTING, INITIALIZED, DB_PATH, _TEST_DB_PATH, SERVICE, LOG_DIR, REQUEST_LOG_DIR
    TESTING = True
    INITIALIZED = True
    SERVICE = service
    if test_db_path:
        _TEST_DB_PATH = test_db_path
    DB_PATH = _TEST_DB_PATH
    
    # Update log directories based on service
    LOG_DIR = get_log_dir()
    REQUEST_LOG_DIR = os.path.join(LOG_DIR, "requests")

def init_production(service: Optional[str] = None) -> None:
    """
    Initialize system for production mode.
    
    :param service: Optional service name (trakaido, blog, spaceship)
    """
    global TESTING, INITIALIZED, DB_PATH, SERVICE, LOG_DIR, REQUEST_LOG_DIR
    TESTING = False
    INITIALIZED = True
    SERVICE = service
    DB_PATH = _PROD_DB_PATH
    
    # Update log directories based on service
    LOG_DIR = get_log_dir()
    REQUEST_LOG_DIR = os.path.join(LOG_DIR, "requests")

def reset() -> None:
    """Reset to uninitialized state (primarily for testing)."""
    global TESTING, INITIALIZED, DB_PATH, _TEST_DB_PATH, SERVICE, LOG_DIR, REQUEST_LOG_DIR
    TESTING = False
    INITIALIZED = False
    SERVICE = None
    DB_PATH = _PROD_DB_PATH
    _TEST_DB_PATH = None
    
    # Reset log directories to default
    LOG_DIR = get_log_dir()
    REQUEST_LOG_DIR = os.path.join(LOG_DIR, "requests")
