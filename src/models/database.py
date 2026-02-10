"""Database connection and session management."""

import time
from contextlib import contextmanager
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, Session
from typing import Optional, Generator

import constants
from common.base.logging_config import get_logger
logger = get_logger(__name__)


def upgrade_schema(engine) -> None:
    """
    Apply schema upgrades for columns added after initial table creation.

    SQLAlchemy's create_all() only creates new tables, not new columns on existing tables.
    This function checks for missing columns and adds them.
    """
    inspector = inspect(engine)

    # Define columns that may need to be added to existing tables
    # Format: (table_name, column_name, column_type)
    schema_upgrades = [
        ('emails', 'public_content', 'TEXT'),
        ('emails', 'public_processed_content', 'TEXT'),
        ('emails', 'english_annotations', 'TEXT'),
    ]

    with engine.connect() as conn:
        for table_name, column_name, column_type in schema_upgrades:
            # Check if table exists
            if table_name not in inspector.get_table_names():
                continue

            # Check if column already exists
            existing_columns = [col['name'] for col in inspector.get_columns(table_name)]
            if column_name in existing_columns:
                continue

            # Add the missing column
            logger.info(f"Adding column {column_name} to table {table_name}")
            try:
                conn.execute(text(f'ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}'))
                conn.commit()
            except Exception as e:
                logger.warning(f"Could not add column {column_name} to {table_name}: {e}")

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

        Supports both SQLite (default) and PostgreSQL/Supabase (via DATABASE_URL).
        When using PostgreSQL, connection pooling is enabled for better performance.

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
                db_url = constants.get_database_url()

            # Configure engine based on database type
            engine_kwargs = {}
            if db_url and db_url.startswith('postgresql'):
                # PostgreSQL/Supabase connection pooling settings
                engine_kwargs = {
                    'pool_size': 5,
                    'max_overflow': 10,
                    'pool_timeout': 30,
                    'pool_recycle': 1800,  # Recycle connections after 30 minutes
                    'pool_pre_ping': True,  # Verify connections before use
                }
                logger.info("Using PostgreSQL database with connection pooling")
            else:
                logger.info(f"Using SQLite database: {db_url}")

            self._engine = create_engine(db_url, **engine_kwargs)

            # Import here to avoid circular imports
            from models import Base
            Base.metadata.create_all(self._engine)

            # Apply any pending schema upgrades (new columns on existing tables)
            upgrade_schema(self._engine)

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
        start_time = time.time()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Session error: {str(e)}")
            # Record database error metric
            try:
                from atacama.blueprints.metrics import record_db_error
                record_db_error()
            except ImportError:
                pass  # Metrics not available (e.g., during testing)
            raise
        finally:
            session.close()
            # Record session duration metric
            duration = time.time() - start_time
            try:
                from atacama.blueprints.metrics import record_db_session_duration
                record_db_session_duration(duration)
            except ImportError:
                pass  # Metrics not available (e.g., during testing)

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
