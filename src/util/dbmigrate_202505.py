#!/usr/bin/env python3
"""
Migrate from old emails table to new messages/emails inheritance structure.
Preserves original email IDs.
"""

import sys
from sqlalchemy import create_engine, MetaData, Table, Column, Integer, String, DateTime, Boolean, Text, ForeignKey, Enum, text
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from typing import Optional, Any

# Import the new models
from models import MessageType
from models.database import db

def ensure_datetime(value: Any) -> Optional[datetime]:
    """Convert various formats to datetime or None."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        # Try to parse common datetime formats
        for fmt in [
            '%Y-%m-%d %H:%M:%S.%f',
            '%Y-%m-%d %H:%M:%S',
            '%Y-%m-%d',
        ]:
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue
    return None

def create_new_tables(engine):
    """Create the new messages table structure."""
    metadata = MetaData()
    
    # Create messages table with identity insert capability
    messages_table = Table('messages', metadata,
        Column('id', Integer, primary_key=True, autoincrement=False),  # autoincrement=False allows explicit IDs
        Column('message_type', Enum(MessageType), nullable=False),
        Column('created_at', DateTime, default=datetime.utcnow),
        Column('last_modified_at', DateTime, default=datetime.utcnow),
        Column('channel', String, nullable=False),
        Column('author_id', Integer, ForeignKey('users.id'), nullable=False)
    )
    
    # Create new emails table structure
    emails_new_table = Table('emails_new', metadata,
        Column('id', Integer, ForeignKey('messages.id'), primary_key=True),
        Column('subject', String),
        Column('content', Text),
        Column('preview_content', Text),
        Column('processed_content', Text),
        Column('parent_id', Integer, ForeignKey('emails_new.id')),
        Column('chinese_annotations', Text),
        Column('llm_annotations', Text)
    )
    
    metadata.create_all(engine)
    return messages_table, emails_new_table

def migrate_data(source_engine):
    """Migrate data from old structure to new structure, preserving IDs."""
    # Create sessions
    Session = sessionmaker(bind=source_engine)
    session = Session()
    
    try:
        # Create the new tables
        print("Creating new table structure...")
        messages_table, emails_new_table = create_new_tables(source_engine)
        
        # Read all existing emails using a more explicit query
        print("Reading existing emails...")
        result = session.execute(text("""
            SELECT id, subject, content, preview_content, processed_content, 
                   created_at, channel, author_id, parent_id, 
                   chinese_annotations, llm_annotations
            FROM emails 
            ORDER BY id
        """))
        old_emails = result.fetchall()
        
        print(f"Found {len(old_emails)} emails to migrate")
        
        # Get the max ID to ensure we can reset autoincrement later
        max_id = session.execute(text("SELECT MAX(id) FROM emails")).scalar() or 0
        
        # Migrate emails with their original IDs
        print("Migrating emails with original IDs...")
        for row in old_emails:
            # Parse datetime value
            created_at = ensure_datetime(row.created_at) or datetime.utcnow()
            
            # Insert into messages table with explicit ID
            message_insert = messages_table.insert().values(
                id=row.id,  # Use original ID
                message_type=MessageType.EMAIL,
                created_at=created_at,
                last_modified_at=created_at,  # Use created_at as initial value
                channel=row.channel or 'private',
                author_id=row.author_id
            )
            session.execute(message_insert)
            
            # Insert into emails_new table with same ID
            email_insert = emails_new_table.insert().values(
                id=row.id,  # Use original ID
                subject=row.subject,
                content=row.content,
                preview_content=row.preview_content,
                processed_content=row.processed_content,
                parent_id=row.parent_id,  # Keep original parent_id
                chinese_annotations=row.chinese_annotations,
                llm_annotations=row.llm_annotations
            )
            session.execute(email_insert)
        
        print("Migration complete with preserved IDs")
        
        # Update the autoincrement sequence for messages table
        print(f"Setting autoincrement to start after {max_id}...")
        # For SQLite
        try:
            session.execute(text(f"UPDATE sqlite_sequence SET seq = {max_id} WHERE name = 'messages'"))
        except Exception as e:
            print(f"Note: Could not update sqlite_sequence: {e}")
            # This might not exist if no autoincrement has been used yet
        
        # Rename tables
        print("Renaming tables...")
        session.execute(text("ALTER TABLE emails RENAME TO emails_old"))
        session.execute(text("ALTER TABLE emails_new RENAME TO emails"))
        
        # Quote relationships already have correct IDs, no migration needed
        print("Quote relationships preserved (no ID changes)")
        
        session.commit()
        print("Migration complete!")
        
        # Verify the migration
        print("\nVerification:")
        message_count = session.execute(text("SELECT COUNT(*) FROM messages")).scalar()
        email_count = session.execute(text("SELECT COUNT(*) FROM emails")).scalar()
        print(f"Messages table: {message_count} rows")
        print(f"Emails table: {email_count} rows")
        
        # Check ID preservation
        id_check = session.execute(text("""
            SELECT COUNT(*) FROM messages m 
            JOIN emails e ON m.id = e.id 
            WHERE m.id IN (SELECT id FROM emails_old)
        """)).scalar()
        print(f"ID preservation check: {id_check} matching IDs")
        
        # Clean up
        response = input("\nDo you want to drop the old emails table? (y/n): ")
        if response.lower() == 'y':
            session.execute(text("DROP TABLE emails_old"))
            session.commit()
            print("Old emails table dropped")
        else:
            print("Old emails table kept as 'emails_old'")
        
    except Exception as e:
        print(f"Error during migration: {e}")
        session.rollback()
        raise
    finally:
        session.close()

def main():
    """Main migration function."""
    # Get database path from constants
    import constants
    constants.init_production()  # Initialize for production
    
    db_path = f'sqlite:///{constants.DB_PATH}'
    print(f"Connecting to database: {db_path}")
    
    # Create engine
    engine = create_engine(db_path)
    
    # Run migration
    migrate_data(engine)

if __name__ == "__main__":
    main()