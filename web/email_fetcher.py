import imaplib
import email
import threading
import time
import json
import logging
from email.header import decode_header
from typing import Optional

from common.models import Email
from common.colorscheme import ColorScheme

logger = logging.getLogger(__name__)
color_processor = ColorScheme()

class EmailFetcher:
    def __init__(self, host: str = 'localhost', port: int = 143, username: Optional[str] = None, password: Optional[str] = None):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        
    def connect(self) -> bool:
        """Establish IMAP connection."""
        try:
            self.imap = imaplib.IMAP4(self.host, self.port)
            if self.username and self.password:
                self.imap.login(self.username, self.password)
            return True
        except Exception as e:
            logger.error(f"IMAP connection failed: {str(e)}")
            return False

    def fetch_emails(self, session) -> None:
        """Fetch and process new emails."""
        try:
            if not self.connect():
                return
            
            self.imap.select('INBOX')
            _, messages = self.imap.search(None, 'UNSEEN')
            
            for msg_num in messages[0].split():
                try:
                    _, msg_data = self.imap.fetch(msg_num, '(RFC822)')
                    email_body = msg_data[0][1]
                    msg = email.message_from_bytes(email_body)
                    
                    subject = decode_header(msg['subject'])[0][0]
                    if isinstance(subject, bytes):
                        subject = subject.decode()
                    
                    content = ""
                    if msg.is_multipart():
                        for part in msg.walk():
                            if part.get_content_type() == "text/plain":
                                content += part.get_payload(decode=True).decode()
                    else:
                        content = msg.get_payload(decode=True).decode()
                    
                    processed_content = color_processor.process_content(content)
                    email_obj = Email(
                        subject=subject,
                        content=content,
                        processed_content=processed_content
                    )
                    
                    session.add(email_obj)
                    session.commit()
                    
                    logger.info(f"Processed incoming email: {subject}")
                    
                except Exception as e:
                    logger.error(f"Error processing message {msg_num}: {str(e)}")
                    continue
                    
        except Exception as e:
            logger.error(f"Error in fetch_emails: {str(e)}")
        
        finally:
            try:
                self.imap.close()
                self.imap.logout()
            except:
                pass

class EmailFetcherDaemon(threading.Thread):
    def __init__(self, config_path: str = 'email_config.json'):
        super().__init__(daemon=True)
        self.config_path = config_path
        self.running = True
        self.load_config()
        
    def load_config(self) -> None:
        """Load IMAP configuration from file."""
        try:
            with open(self.config_path) as f:
                config = json.load(f)
            self.interval = config.get('fetch_interval', 300)  # default 5 minutes
            self.imap_config = {
                'host': config.get('host', 'localhost'),
                'port': config.get('port', 143),
                'username': config.get('username'),
                'password': config.get('password')
            }
        except Exception as e:
            logger.error(f"Error loading config: {str(e)}")
            self.interval = 300
            self.imap_config = {
                'host': 'localhost',
                'port': 143,
                'username': None,
                'password': None
            }

    def run(self) -> None:
        """Run the email fetcher daemon."""
        logger.info("Starting email fetcher daemon...")
        fetcher = EmailFetcher(**self.imap_config)
        
        while self.running:
            session = Session()
            try:
                fetcher.fetch_emails(session)
            except Exception as e:
                logger.error(f"Error in fetcher daemon: {str(e)}")
            finally:
                session.close()
            
            time.sleep(self.interval)
    
    def stop(self) -> None:
        """Stop the daemon gracefully."""
        self.running = False
