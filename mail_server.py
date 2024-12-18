from sqlalchemy import Column, Integer, String, Boolean, ForeignKey
from sqlalchemy.orm import relationship
import asyncio
import logging
import ssl
from aiosmtpd.controller import Controller
from aiosmtpd.smtp import SMTP, AuthResult, LoginPassword
from email.message import EmailMessage
from email.utils import formatdate
import bcrypt
from typing import Optional

class MailUser(Base):
    __tablename__ = 'mail_users'
    
    id = Column(Integer, primary_key=True)
    username = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    active = Column(Boolean, default=True)
    
    def verify_password(self, password: str) -> bool:
        return bcrypt.checkpw(password.encode('utf-8'), self.password_hash.encode('utf-8'))
    
    @staticmethod
    def hash_password(password: str) -> str:
        return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

class AuthenticatedSMTP(SMTP):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.session = Session()
        
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
            logging.error(f"Authentication error: {str(e)}")
        return AuthResult(success=False)

class MailHandler:
    def __init__(self):
        self.session = Session()
        self.processor = EmailProcessor()
    
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
            
            # Process the email using existing Atacama infrastructure
            email_obj = Email(
                subject=message.get('subject', 'No Subject'),
                content=message.get_content(),
                processed_content=self.processor.process_email(message.get_content())
            )
            
            self.session.add(email_obj)
            self.session.commit()
            
            return '250 Message accepted for delivery'
            
        except Exception as e:
            logging.error(f"Error processing mail: {str(e)}")
            return '554 5.3.0 Transaction failed'
        
        finally:
            self.session.close()

class MailServer:
    def __init__(self, host='0.0.0.0', port=587):
        self.host = host
        self.port = port
        self.handler = MailHandler()
        self.ssl_context = self._create_ssl_context()
        
    def _create_ssl_context(self) -> ssl.SSLContext:
        context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        context.load_cert_chain('/etc/atacama/mail/cert.pem', '/etc/atacama/mail/key.pem')
        return context
    
    def run(self):
        controller = Controller(
            handler=self.handler,
            hostname=self.host,
            port=self.port,
            ssl_context=self.ssl_context,
            server_class=AuthenticatedSMTP
        )
        
        try:
            controller.start()
            logging.info(f"Mail server running on {self.host}:{self.port}")
            asyncio.get_event_loop().run_forever()
        except KeyboardInterrupt:
            controller.stop()
