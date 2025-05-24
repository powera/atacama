"""
Migration script to move quotes into the messages table.

This script will:
1. Rename the current quotes table to old_quotes
2. Create a new quotes table with the updated schema
3. Migrate the data from old_quotes to quotes while maintaining relationships
"""
import os
import sys
from datetime import datetime
from sqlalchemy import create_engine, text, Column, Integer, String, Text, DateTime, ForeignKey, Table
from sqlalchemy.orm import sessionmaker, relationship

# Add the src directory to the Python path
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'src'))

# Import models to ensure all tables are registered with SQLAlchemy
from models.models import Base, Quote, Email, Article, MessageType
from config import get_database_url

def get_db_session():
    """Create and return a database session."""
    engine = create_engine(get_database_url())
    Session = sessionmaker(bind=engine)
    return Session()

def migrate_quotes():
    """Perform the migration of quotes to the messages table."""
    print("Starting quotes migration...")
    
    # Create a database session
    session = get_db_session()
    
    try:
        # Begin transaction
        session.begin()
        
        # 1. Rename the current quotes table to old_quotes
        print("Renaming quotes table to old_quotes...")
        session.execute(text("ALTER TABLE quotes RENAME TO old_quotes;"))
        
        # 2. Create the new quotes table with the updated schema
        print("Creating new quotes table...")
        
        # Create the new quotes table
        session.execute(text("""
            CREATE TABLE quotes (
                id INTEGER NOT NULL,
                text TEXT NOT NULL,
                quote_type VARCHAR,
                author VARCHAR,
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
        
        for quote in old_quotes:
            # Insert into messages table first
            result = session.execute(text("""
                INSERT INTO messages (message_type, created_at, last_modified_at, channel, author_id)
                VALUES (:message_type, :created_at, :last_modified, :channel, 1)
                RETURNING id;
            """), {
                'message_type': 'quote',
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
        
        # 4. Recreate the foreign key constraints with CASCADE
        print("Recreating foreign key constraints...")
        session.execute(text("""
            -- Drop existing foreign key constraints
            PRAGMA foreign_keys=off;
            
            -- Recreate the email_quotes table with CASCADE
            CREATE TABLE email_quotes_new (
                email_id INTEGER NOT NULL,
                quote_id INTEGER NOT NULL,
                created_at DATETIME,
                PRIMARY KEY (email_id, quote_id),
                FOREIGN KEY(email_id) REFERENCES emails (id) ON DELETE CASCADE,
                FOREIGN KEY(quote_id) REFERENCES quotes (id) ON DELETE CASCADE
            );
            
            -- Copy data to the new table
            INSERT INTO email_quotes_new SELECT * FROM email_quotes;
            
            -- Drop the old table and rename the new one
            DROP TABLE email_quotes;
            ALTER TABLE email_quotes_new RENAME TO email_quotes;
            
            -- Drop the article_quotes table as it's no longer needed
            DROP TABLE IF EXISTS article_quotes;
            
            PRAGMA foreign_keys=on;
            
            -- Drop the old_quotes table
            DROP TABLE IF EXISTS old_quotes;
            
            -- Update the database statistics
            ANALYZE;
            VACUUM;
        
            -- Commit the transaction
            COMMIT;
        
            -- Notify the user that the migration was successful
            SELECT 'Migration completed successfully!' as message;
        
        """))
        
        print("Migration completed successfully!")
        
    except Exception as e:
        session.rollback()
        print(f"Error during migration: {e}")
        raise
    finally:
        session.close()

if __name__ == "__main__":
    print("Starting quotes migration script...")
    migrate_quotes()
    print("Script completed.")
