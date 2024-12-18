import asyncio
import logging
import ssl
from aiosmtpd.controller import Controller
from aiosmtpd.smtp import SMTP, AuthResult, LoginPassword
from email.message import EmailMessage
from email.utils import formatdate
from typing import Optional

from common.database import setup_database
from common.models import Email, MailUser
from common.colorscheme import ColorScheme

logger = logging.getLogger(__name__)
Session, db_success = setup_database()

class AuthenticatedSMTP(SMTP):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.session = Session()
        self.authenticated = False
        self.authenticated_user = None
        
    async def smtp_AUTH(self, arg):
        if not arg:
            return '501 Syntax error in parameters or arguments'
        
        auth_type = arg.split()[0].upper()
        if auth_type != 'LOGIN':
            return '504 Unrecognized authentication type'
            
        auth_handler = LoginPassword()
        result = await auth_handler.handle_LOGIN(self, arg)
        
        if result.success:
            self.authenticated = True
            self.authenticated_user = result.auth_data
            return '235 2.7.0 Authentication successful'
        return '535 5.7.8 Authentication credentials invalid'
    
    async def validate_auth(self, username: str, password: str) -> AuthResult:
        try:
            user = self.session.query(MailUser).filter_by(username=username, active=True).first()
            if user and user.verify_password(password):
                return AuthResult(success=True, auth_data=username)
        except Exception as e:
            logger.error(f"Authentication error: {str(e)}")
        return AuthResult(success=False)

class MailHandler:
    def __init__(self):
        self.session = Session()
        self.color_processor = ColorScheme()
    
    async def handle_MAIL(self, server, session, envelope, address, mail_options):
        if not server.authenticated:
            return '530 5.7.0 Authentication required'
        envelope.mail_from = address
        return '250 Sender OK'
    
    async def handle_RCPT(self, server, session, envelope, address, rcpt_options):
        if not server.authenticated:
            return '530 5.7.0 Authentication required'
        envelope.rcpt_tos.append(address)
        return '250 Recipient OK'
    
    async def handle_DATA(self, server, session, envelope):
        if not server.authenticated:
            return '530 5.7.0 Authentication required'
            
        try:
            message = EmailMessage()
            message['From'] = envelope.mail_from
            message['To'] = ', '.join(envelope.rcpt_tos)
            message['Date'] = formatdate(localtime=True)
            message.set_content(envelope.content.decode('utf-8'))
            
            content = message.get_content()
            processed_content = self.color_processor.process_content(content)
            
            email_obj = Email(
                subject=message.get('subject', 'No Subject'),
                content=content,
                processed_content=processed_content
            )
            
            self.session.add(email_obj)
            self.session.commit()
            
            return '250 Message accepted for delivery'
            
        except Exception as e:
            logger.error(f"Error processing mail: {str(e)}")
            return '554 5.3.0 Transaction failed'
        
        finally:
            self.session.close()

class MailServer:
    def __init__(self, host: str = '0.0.0.0', port: int = 587):
        """
        Initialize mail server.
        
        :param host: Host address to bind to
        :param port: Port to listen on
        """
        self.host = host
        self.port = port
        self.handler = MailHandler()
        self.ssl_context = self._create_ssl_context()
        
    def _create_ssl_context(self) -> ssl.SSLContext:
        """Create SSL context for secure connections."""
        context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        context.load_cert_chain('/etc/atacama/mail/cert.pem', '/etc/atacama/mail/key.pem')
        return context
    
    def run(self) -> None:
        """Run the mail server."""
        if not db_success:
            logger.error("Database initialization failed, cannot start mail server")
            return
            
        controller = Controller(
            handler=self.handler,
            hostname=self.host,
            port=self.port,
            ssl_context=self.ssl_context,
            server_class=AuthenticatedSMTP
        )
        
        try:
            controller.start()
            logger.info(f"Mail server running on {self.host}:{self.port}")
            asyncio.get_event_loop().run_forever()
        except KeyboardInterrupt:
            controller.stop()

def add_user(self, username: str, password: str) -> bool:
    """
    Add a new mail user to the system.
    
    :param username: Username for the new mail user
    :param password: Password for the new mail user
    :return: True if user was added successfully, False otherwise
    """
    try:
        session = Session()
        
        # Check if user already exists
        existing_user = session.query(MailUser).filter_by(username=username).first()
        if existing_user:
            logger.warning(f"User {username} already exists")
            return False
            
        # Create new user with hashed password
        user = MailUser(
            username=username,
            password_hash=MailUser.hash_password(password),
            active=True
        )
        
        session.add(user)
        session.commit()
        logger.info(f"Added new mail user: {username}")
        return True
        
    except Exception as e:
        logger.error(f"Error adding mail user {username}: {str(e)}")
        return False
        
    finally:
        session.close()
