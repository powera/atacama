#!/usr/bin/env python3

"""Atacama System Launch Script."""

import os
import sys
import argparse
import datetime
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

import constants
from common.base.logging_config import configure_logging, get_logger
from common.config.channel_config import init_channel_manager
from common.config.domain_config import init_domain_manager

def get_log_filename():
    """
    Generate a log filename including PID and datetime.
    
    :return: Formatted log filename string
    """
    import datetime
    pid = os.getpid()
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"atacama_{timestamp}_pid{pid}.log"

def init_system(log_level="INFO", app_log_level="DEBUG"):
    """Initialize system components."""
    constants.init_production()
    
    # Create a unique log filename with PID and timestamp
    log_filename = get_log_filename()
    
    configure_logging(
        log_level=log_level,
        app_log_level=app_log_level,
        log_filename=log_filename
    )
    
    logger = get_logger(__name__)
    logger.info(f"Starting with PID {os.getpid()}, log file: {log_filename}")
    
    # Initialize config managers
    init_channel_manager()
    init_domain_manager()

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Launch Atacama system components.',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    # Component selection
    parser.add_argument('--mode', choices=['web', 'spaceship'], 
                      help='Server mode to run (web or spaceship)')
    parser.add_argument('--web', action='store_true', help='Launch web server')
    parser.add_argument('--spaceship', action='store_true', help='Launch spaceship server')
    
    # Server configuration
    parser.add_argument('--host', default='0.0.0.0', help='Host for server')
    parser.add_argument('--port', type=int, help='Port for server')
    
    # Logging configuration
    parser.add_argument('--log-level', default='INFO',
                       choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                       help='Set the logging level')
    parser.add_argument('--app-log-level', default='DEBUG',
                       choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                       help='Set the application-specific logging level')
    
    # Note about log files
    parser.epilog = "Note: Log files are created with timestamp and PID in the filename format: atacama_YYYYMMDD_HHMMSS_pidNNNN.log"
    
    return parser.parse_args()

def main():
    """Main entry point."""
    args = parse_args()
    
    # Determine which mode to run based on arguments
    if args.mode:
        # Legacy mode argument support
        if args.mode == 'web':
            args.web = True
            args.spaceship = False
        elif args.mode == 'spaceship':
            args.spaceship = True
            args.web = False
    
    # Initialize system with configured log levels
    init_system(log_level=args.log_level, app_log_level=args.app_log_level)
    
    # Get logger after initialization to ensure it's properly configured
    logger = get_logger(__name__)
    logger.info("Atacama system initialized")
    
    # Launch requested components
    if args.web:
        from web.server import run_server
        port = args.port or 5000
        logger.info(f"Starting web server on {args.host}:{port}")
        run_server(host=args.host, port=port)
    elif args.spaceship:
        from spaceship.server import run_server
        port = args.port or 8998
        logger.info(f"Starting spaceship server on {args.host}:{port}")
        run_server(args.host, port)
    else:
        print("No component specified to launch. Use --web or --spaceship to start a server.")
        return 1
    
    return 0

if __name__ == '__main__':
    sys.exit(main())