from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
import bcrypt

Base = declarative_base()

class Email(Base):
    """Email model storing both original and processed content."""
    __tablename__ = 'emails'
    
    id = Column(Integer, primary_key=True)
    subject = Column(String(255))
    content = Column(Text)
    processed_content = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

class MailUser(Base):
    """Mail user model for SMTP authentication."""
    __tablename__ = 'mail_users'
    
    id = Column(Integer, primary_key=True)
    username = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    active = Column(Boolean, default=True)
    
    def verify_password(self, password: str) -> bool:
        """
        Verify a password against the stored hash.
        
        :param password: Plain text password to verify
        :return: True if password matches, False otherwise
        """
        return bcrypt.checkpw(password.encode('utf-8'), self.password_hash.encode('utf-8'))
    
    @staticmethod
    def hash_password(password: str) -> str:
        """
        Hash a password for storage.
        
        :param password: Plain text password to hash
        :return: Hashed password string
        """
        return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
