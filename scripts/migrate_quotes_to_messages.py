"""
Migration script to move quotes into the messages table.

This script will:
1. Rename the current quotes table to old_quotes
2. Create a new quotes table with the updated schema
3. Migrate the data from old_quotes to quotes while maintaining relationships
"""
import os
import sys
import enum
from datetime import datetime
from sqlalchemy import create_engine, text, Column, Integer, String, Text, DateTime, ForeignKey, Table
from sqlalchemy.orm import sessionmaker, relationship

# Add the src directory to the Python path
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'src'))

# Import only constants, avoid importing any models to prevent schema conflicts
import constants

# Define the MessageType enum locally to avoid importing models
class MessageType(enum.Enum):
    EMAIL = "email"
    ARTICLE = "article"
    WIDGET = "widget"
    QUOTE = "quote"

def get_db_session():
    """Create and return a database session."""
    # Initialize the system in production mode
    constants.init_production()
    
    # Get the database URL directly from constants
    if constants.TESTING:
        db_url = constants._TEST_DB_PATH
    else:
        db_url = f'sqlite:///{constants._PROD_DB_PATH}'
    
    # Create engine and session directly
    engine = create_engine(db_url)
    Session = sessionmaker(bind=engine)
    return Session()

def migrate_quotes():
    """Perform the migration of quotes to the messages table."""
    print("Starting quotes migration...")
    
    # Create a database session
    session = get_db_session()
    
    try:
        # 1. Rename the current quotes table to old_quotes
        # Note: This will auto-commit in SQLite
        print("Renaming quotes table to old_quotes...")
        session.execute(text("ALTER TABLE quotes RENAME TO old_quotes;"))
        
        # 2. Create the new quotes table with the updated schema
        # Note: This will auto-commit in SQLite
        print("Creating new quotes table...")
        session.execute(text("""
            CREATE TABLE quotes (
                id INTEGER NOT NULL,
                text TEXT NOT NULL,
                quote_type VARCHAR,
                original_author VARCHAR,  -- Using original_author to match the new schema
                date VARCHAR,
                source TEXT,
                commentary TEXT,
                PRIMARY KEY (id),
                FOREIGN KEY(id) REFERENCES messages (id) ON DELETE CASCADE
            )
        """))
        
        # 3. Get all quotes with their associated emails to determine the channel
        print("Migrating quote data...")
        old_quotes = session.execute(text("""
            SELECT oq.*, 
                   (SELECT channel FROM messages m 
                    JOIN email_quotes eq ON m.id = eq.email_id 
                    WHERE eq.quote_id = oq.id 
                    ORDER BY m.created_at ASC LIMIT 1) as channel
            FROM old_quotes oq
        """)).fetchall()
        
        # Make sure any previous transaction is committed
        session.commit()
        
        print("Starting data migration...")
        try:
            # SQLAlchemy will automatically begin a transaction when needed
            for quote in old_quotes:
                # Insert into messages table first
                result = session.execute(text("""
                    INSERT INTO messages (message_type, created_at, last_modified_at, channel, author_id)
                    VALUES (:message_type, :created_at, :last_modified, :channel, 1)
                    RETURNING id;
                """), {
                    'message_type': 'QUOTE',  # must be uppercase to match the enum
                    'created_at': quote.created_at or datetime.utcnow(),
                    'last_modified': datetime.utcnow(),
                    'channel': quote.channel or 'private'
                })
                
                message_id = result.fetchone()[0]
                
                # Insert into quotes table
                session.execute(text("""
                    INSERT INTO quotes (id, text, quote_type, original_author, date, source, commentary)
                    VALUES (:id, :text, :quote_type, :original_author, :date, :source, :commentary);
                """), {
                    'id': message_id,
                    'text': quote.text,
                    'quote_type': quote.quote_type or 'quote',
                    'original_author': quote.author,  # Map old author to new original_author
                    'date': quote.date,
                    'source': quote.source,
                    'commentary': quote.commentary
                })
                
                # Update the foreign key references in the association tables
                session.execute(text("""
                    UPDATE email_quotes SET quote_id = :new_id WHERE quote_id = :old_id;
                """), {'new_id': message_id, 'old_id': quote.id})
                
                session.execute(text("""
                    UPDATE article_quotes SET quote_id = :new_id WHERE quote_id = :old_id;
                """), {'new_id': message_id, 'old_id': quote.id})
            
            # Commit the data migration transaction
            session.commit()
            print("Data migration completed successfully.")
        except Exception as e:
            session.rollback()
            print(f"Error during data migration: {e}")
            raise
        
        # 4. Recreate the foreign key constraints with CASCADE
        # Note: These schema changes will auto-commit in SQLite
        print("Recreating foreign key constraints...")
        
        # Turn off foreign keys
        session.execute(text("PRAGMA foreign_keys=off;"))
        
        # Recreate the email_quotes table with CASCADE
        session.execute(text("""
            CREATE TABLE email_quotes_new (
                email_id INTEGER NOT NULL,
                quote_id INTEGER NOT NULL,
                created_at DATETIME,
                PRIMARY KEY (email_id, quote_id),
                FOREIGN KEY(email_id) REFERENCES emails (id) ON DELETE CASCADE,
                FOREIGN KEY(quote_id) REFERENCES quotes (id) ON DELETE CASCADE
            );
        """))
        
        # Make sure any previous transaction is committed
        session.commit()
        
        try:
            # Copy data to the new table
            session.execute(text("INSERT INTO email_quotes_new SELECT * FROM email_quotes;"))
            session.commit()
            print("Association table data copied successfully.")
        except Exception as e:
            session.rollback()
            print(f"Error copying association table data: {e}")
            raise
        
        # Continue with schema changes (these auto-commit)
        # Drop the old table and rename the new one
        session.execute(text("DROP TABLE email_quotes;"))
        session.execute(text("ALTER TABLE email_quotes_new RENAME TO email_quotes;"))
        
        # Drop the article_quotes table as it's no longer needed
        session.execute(text("DROP TABLE IF EXISTS article_quotes;"))
        
        # Turn foreign keys back on
        session.execute(text("PRAGMA foreign_keys=on;"))
        
        # Drop the old_quotes table
        session.execute(text("DROP TABLE IF EXISTS old_quotes;"))
        
        # Update the database statistics
        session.execute(text("ANALYZE;"))
        
        print("Migration completed successfully!")
        
    except Exception as e:
        print(f"Error during migration: {e}")
        raise
    finally:
        session.close()

if __name__ == "__main__":
    print("Starting quotes migration script...")
    migrate_quotes()
    print("Script completed.")
