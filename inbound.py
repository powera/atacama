from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import re
from typing import Dict, List
from flask import Flask, request, jsonify
import logging
from waitress import serve
import imaplib
import email
import threading
import time
import os
from email.header import decode_header
import json

app = Flask(__name__)
Base = declarative_base()

# [Previous ColorScheme and Email classes remain the same]
[Previous code for ColorScheme and Email classes]

class EmailFetcher:
    def __init__(self, host='localhost', port=143, username=None, password=None):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.processor = EmailProcessor()
        self.logger = logging.getLogger(__name__)
        
    def connect(self):
        """Establish IMAP connection."""
        try:
            self.imap = imaplib.IMAP4(self.host, self.port)
            if self.username and self.password:
                self.imap.login(self.username, self.password)
            return True
        except Exception as e:
            self.logger.error(f"IMAP connection failed: {str(e)}")
            return False

    def fetch_emails(self, session):
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
                    
                    # Extract content from email
                    content = ""
                    if msg.is_multipart():
                        for part in msg.walk():
                            if part.get_content_type() == "text/plain":
                                content += part.get_payload(decode=True).decode()
                    else:
                        content = msg.get_payload(decode=True).decode()
                    
                    # Process and store email
                    processed_content = self.processor.process_email(content)
                    email_obj = Email(
                        subject=subject,
                        content=content,
                        processed_content=processed_content
                    )
                    
                    session.add(email_obj)
                    session.commit()
                    
                    self.logger.info(f"Processed incoming email: {subject}")
                    
                except Exception as e:
                    self.logger.error(f"Error processing message {msg_num}: {str(e)}")
                    continue
                    
        except Exception as e:
            self.logger.error(f"Error in fetch_emails: {str(e)}")
        
        finally:
            try:
                self.imap.close()
                self.imap.logout()
            except:
                pass

class EmailFetcherDaemon(threading.Thread):
    def __init__(self, config_path='email_config.json'):
        super().__init__(daemon=True)
        self.logger = logging.getLogger(__name__)
        self.config_path = config_path
        self.running = True
        self.load_config()
        
    def load_config(self):
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
            self.logger.error(f"Error loading config: {str(e)}")
            # Use defaults if config loading fails
            self.interval = 300
            self.imap_config = {
                'host': 'localhost',
                'port': 143,
                'username': None,
                'password': None
            }

    def run(self):
        """Run the email fetcher daemon."""
        self.logger.info("Starting email fetcher daemon...")
        fetcher = EmailFetcher(**self.imap_config)
        
        while self.running:
            session = Session()
            try:
                fetcher.fetch_emails(session)
            except Exception as e:
                self.logger.error(f"Error in fetcher daemon: {str(e)}")
            finally:
                session.close()
            
            time.sleep(self.interval)
    
    def stop(self):
        """Stop the daemon gracefully."""
        self.running = False

def run_server():
    """Run the server and start the email fetcher daemon."""
    # Start email fetcher daemon
    fetcher_daemon = EmailFetcherDaemon()
    fetcher_daemon.start()
    
    logger.info("Starting email processor server...")
    try:
        serve(app, host='0.0.0.0', port=5000)
    finally:
        # Ensure daemon is stopped when server stops
        fetcher_daemon.stop()
        fetcher_daemon.join()

if __name__ == "__main__":
    run_server()
