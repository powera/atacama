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

def init_system(log_level="INFO", app_log_level="DEBUG", service=None):
    """Initialize system components."""
    constants.init_production(service=service)
    
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
        formatter_class=argparse.RawDescriptionHelpFormatter,
        prog='launch.py'
    )
    
    # Component selection
    parser.add_argument('--mode', choices=['web', 'trakaido', 'spaceship'], 
                      help='Server mode to run (web, trakaido, or spaceship)')
    parser.add_argument('--web', action='store_true', help='Launch web server (blog)')
    parser.add_argument('--trakaido', action='store_true', help='Launch trakaido API server')
    parser.add_argument('--spaceship', action='store_true', help='Launch spaceship server')
    
    # Server configuration
    parser.add_argument('--host', default='0.0.0.0', 
                       help='Host for server (default: 0.0.0.0)')
    parser.add_argument('--port', type=int, 
                       help='Port for server (default: 5000 for web, 5001 for trakaido, 8998 for spaceship)')
    
    # Development options
    parser.add_argument('--dev', action='store_true', 
                       help='Enable development mode with auto-reload')
    parser.add_argument('--debug', action='store_true', 
                       help='Enable debug mode')
    
    # Logging configuration
    parser.add_argument('--log-level', default='INFO',
                       choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                       help='Set the logging level (default: INFO)')
    parser.add_argument('--app-log-level', default='DEBUG',
                       choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                       help='Set the application-specific logging level (default: DEBUG)')
    parser.add_argument('--quiet', '-q', action='store_true',
                       help='Suppress non-essential output')
    
    # Examples and notes
    parser.epilog = """
Examples:
  %(prog)s --web                    # Launch web server (blog) on default port 5000
  %(prog)s --trakaido              # Launch trakaido API server on default port 5001
  %(prog)s --web --port 8080        # Launch web server on port 8080
  %(prog)s --spaceship             # Launch spaceship server
  %(prog)s --mode web --dev        # Launch web server in development mode
  %(prog)s --mode trakaido --dev   # Launch trakaido server in development mode

Note: Log files are created with timestamp and PID in the filename format: 
      atacama_YYYYMMDD_HHMMSS_pidNNNN.log
    """ % {'prog': parser.prog}
    
    return parser.parse_args()

def main():
    """Main entry point."""
    try:
        args = parse_args()
        
        # Determine which mode to run based on arguments
        if args.mode:
            # Legacy mode argument support
            if args.mode == 'web':
                args.web = True
                args.trakaido = False
                args.spaceship = False
            elif args.mode == 'trakaido':
                args.trakaido = True
                args.web = False
                args.spaceship = False
            elif args.mode == 'spaceship':
                args.spaceship = True
                args.web = False
                args.trakaido = False
        
        # Validate arguments
        if not args.web and not args.trakaido and not args.spaceship:
            print("Error: No component specified to launch.", file=sys.stderr)
            print("Use --web, --trakaido, or --spaceship to start a server.", file=sys.stderr)
            print("Run 'python launch.py --help' for more information.", file=sys.stderr)
            return 1
        
        # Count how many server types are specified
        server_count = sum([args.web, args.trakaido, args.spaceship])
        if server_count > 1:
            print("Error: Cannot launch multiple servers simultaneously.", file=sys.stderr)
            return 1
        
        # Determine service for logging purposes
        service = None
        if args.web:
            service = 'blog'
        elif args.trakaido:
            service = 'trakaido'
        elif args.spaceship:
            service = 'spaceship'
        
        # Initialize system with configured log levels
        log_level = 'DEBUG' if args.debug else args.log_level
        if args.quiet:
            log_level = 'WARNING'
            
        init_system(log_level=log_level, app_log_level=args.app_log_level, service=service)
        
        # Get logger after initialization to ensure it's properly configured
        logger = get_logger(__name__)
        logger.info("Atacama system initialized")
        
        # Launch requested components
        if args.web:
            from atacama.server import run_server
            port = args.port or 5000
            if not args.quiet:
                print(f"Starting web server (blog) on http://{args.host}:{port}")
            logger.info(f"Starting web server (blog) on {args.host}:{port}")
            run_server(host=args.host, port=port, debug=args.debug or args.dev, blueprint_set='BLOG')
        elif args.trakaido:
            from atacama.server import run_server
            port = args.port or 5001
            if not args.quiet:
                print(f"Starting trakaido API server on http://{args.host}:{port}")
            logger.info(f"Starting trakaido API server on {args.host}:{port}")
            run_server(host=args.host, port=port, debug=args.debug or args.dev, blueprint_set='TRAKAIDO')
        elif args.spaceship:
            from spaceship.server import run_server
            port = args.port or 8998
            if not args.quiet:
                print(f"Starting spaceship server on {args.host}:{port}")
            logger.info(f"Starting spaceship server on {args.host}:{port}")
            run_server(args.host, port)
        
        return 0
        
    except KeyboardInterrupt:
        print("\nShutdown requested by user", file=sys.stderr)
        return 130  # Standard exit code for SIGINT
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        if '--debug' in sys.argv or '-v' in sys.argv:
            import traceback
            traceback.print_exc()
        return 1

if __name__ == '__main__':
    sys.exit(main())