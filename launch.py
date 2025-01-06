#!/usr/bin/env python3
import argparse
from common.logging_config import configure_logging, get_logger
import sys
from typing import Optional

def run_web_server(host: str = '0.0.0.0', port: int = 5000) -> None:
    """
    Launch the web server component.
    
    :param host: Host address to bind to
    :param port: Port number to listen on
    """
    from web.server import run_server
    run_server(host=host, port=port)

def main() -> None:
    """Main entry point for the Atacama system."""
    parser = argparse.ArgumentParser(description='Atacama System')
    parser.add_argument('--mode', choices=['mail', 'web', 'spaceship'], required=True,
                       help='Server mode to run (mail, web, or spaceship)')
    parser.add_argument('--host', default='0.0.0.0',
                       help='Host address to bind to')
    parser.add_argument('--port', type=int,
                       help='Port number to listen on')
    parser.add_argument('--log-level', default='INFO',
                       choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                       help='Set the logging level')
    
    args = parser.parse_args()
    
    try:
        # Initialize logging with the new configuration
        configure_logging(
            log_level=args.log_level,
            app_log_level='DEBUG',
        )
        logger = get_logger(__name__)
        
        if args.mode == 'mail':
            raise Exception("Mail is not enabled.")
        elif args.mode == 'spaceship':
            from spaceship.server import run_server
            port = args.port or 8998
            logger.info(f'Starting spaceship server on {args.host}:{port}')
            run_server(args.host, port)
        else:  # web mode
            port = args.port or 5000
            logger.info(f'Starting web server on {args.host}:{port}')
            run_web_server(args.host, port)
            
    except Exception as e:
        logger.error(f'Fatal error: {str(e)}')
        sys.exit(1)

if __name__ == '__main__':
    main()
