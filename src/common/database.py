from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from typing import Tuple

from common.logging_config import get_logger
from constants import DB_PATH
logger = get_logger(__name__)


def setup_database(db_url: str = f'sqlite:///{DB_PATH}') -> Tuple[sessionmaker, bool]:
    """
    Initialize database connection and create tables.
    
    :param db_url: SQLAlchemy database URL
    :return: Tuple of (Session maker, success status)
    """
    try:
        engine = create_engine(db_url)
        
        # Import here to avoid circular imports
        from common.models import Base
        Base.metadata.create_all(engine)
        
        Session = sessionmaker(bind=engine)
        return Session, True
        
    except Exception as e:
        logger.error(f"Database setup failed: {str(e)}")
        return None, False
