"""Database connection and session management."""

from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError
from typing import Optional, Generator

import constants
from common.base.logging_config import get_logger
logger = get_logger(__name__)

class DatabaseError(Exception):
    """Custom exception for database-related errors."""
    pass

class Database:
    """Manages database connections and provides session management utilities."""
    
    def __init__(self):
        """Initialize database connection state."""
        self._engine = None
        self._session_factory = None
        self.initialized = False

    def initialize(self) -> bool:
        """
        Initialize database engine and create tables.
        
        :return: True if initialization successful, False otherwise
        :raises: DatabaseError if system not initialized
        """
        if not constants.INITIALIZED:
            raise DatabaseError(
                "Cannot initialize database before system initialization. "
                "Call either constants.init_testing() or constants.init_production()"
            )

        if self.initialized:
            return True
        
        try:
            if constants.TESTING:
                db_url = constants._TEST_DB_PATH
            else:
                db_url = f'sqlite:///{constants._PROD_DB_PATH}'
            
            self._engine = create_engine(db_url)
            
            # Import here to avoid circular imports
            from models import Base
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
        :raises: DatabaseError if database not initialized
        :raises: SQLAlchemyError if database operations fail
        """
        if not constants.INITIALIZED:
            raise DatabaseError(
                "Cannot create database session before system initialization. "
                "Call either constants.init_testing() or constants.init_production()"
            )
            
        if not self.initialized and not self.initialize():
            raise DatabaseError("Database initialization failed")
            
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
        :raises: DatabaseError if system not initialized
        """
        if not constants.INITIALIZED:
            raise DatabaseError(
                "Cannot get session factory before system initialization. "
                "Call either constants.init_testing() or constants.init_production()"
            )
            
        if not self.initialized and not self.initialize():
            return None
        return self._session_factory

    def cleanup(self) -> None:
        """Clean up database connections and reset state."""
        if self._engine:
            self._engine.dispose()
        self._engine = None
        self._session_factory = None
        self.initialized = False

# Global database instance
db = Database()
