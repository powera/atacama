"""Database connection and session management."""

from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError
from typing import Optional, Generator

from common.logging_config import get_logger
from constants import DB_PATH

logger = get_logger(__name__)

class Database:
    """Manages database connections and provides session management utilities."""
    
    def __init__(self, db_url: str = f'sqlite:///{DB_PATH}'):
        """
        Initialize database connection.
        
        :param db_url: SQLAlchemy database URL
        """
        self.db_url = db_url
        self._engine = None
        self._session_factory = None
        self.initialized = False
        self.is_test = False

    def initialize(self, test=False) -> bool:
        """
        Initialize database engine and create tables.
        
        :return: True if initialization successful, False otherwise
        """
        if self.initialized:
            return True
        
        if test:
            self.is_test = True
            self.db_url = "sqlite:///:memory:"

        try:
            self._engine = create_engine(self.db_url)
            
            # Import here to avoid circular imports
            from common.models import Base
            Base.metadata.create_all(self._engine)
            
            self._session_factory = sessionmaker(bind=self._engine)
            self.initialized = True
            return True
            
        except Exception as e:
            logger.error(f"Database initialization failed: {str(e)}")
            return False

    @contextmanager
    def session(self) -> Generator[Session, None, None]:
        """
        Provide a transactional scope around a series of operations.
        
        Usage:
            with db.session() as session:
                session.query(...)
        
        :yield: SQLAlchemy session
        :raises: SQLAlchemyError if database operations fail
        """
        if not self.initialized and not self.initialize():
            raise RuntimeError("Database not initialized")
            
        session = self._session_factory()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Session error: {str(e)}")
            raise
        finally:
            session.close()

    def get_session(self) -> Optional[sessionmaker]:
        """
        Get session factory for manual session management.
        
        :return: SQLAlchemy sessionmaker if initialized, None otherwise
        """
        if not self.initialized and not self.initialize():
            return None
        return self._session_factory

# Global database instance
db = Database()
