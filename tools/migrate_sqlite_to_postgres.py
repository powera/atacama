#!/usr/bin/env python3
"""Migrate Atacama database from SQLite to PostgreSQL/Supabase.

This script copies all data from the local SQLite database to a PostgreSQL
database (e.g., Supabase). It handles the polymorphic Message hierarchy
and all related tables.

Usage:
    # Using keys/database_url file:
    python tools/migrate_sqlite_to_postgres.py

    # Or specify URL directly:
    python tools/migrate_sqlite_to_postgres.py --url "postgresql://..."

    # Dry run (no writes):
    python tools/migrate_sqlite_to_postgres.py --dry-run
"""

import argparse
import os
import sys
from typing import Optional

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "src"))

import constants
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker


def get_postgres_url(url_arg: Optional[str] = None) -> str:
    """
    Get PostgreSQL URL from argument, file, or environment.

    :param url_arg: URL passed as command line argument
    :return: PostgreSQL connection URL
    :raises: ValueError if no URL found
    """
    if url_arg:
        url = url_arg
    else:
        # Try keys/database_url file
        db_url_path = os.path.join(constants.KEY_DIR, 'database_url')
        if os.path.exists(db_url_path):
            with open(db_url_path, 'r') as f:
                url = f.read().strip()
        else:
            # Fall back to environment variable
            url = os.getenv('DATABASE_URL')

    if not url:
        raise ValueError(
            "No PostgreSQL URL found. Provide --url argument, "
            "create keys/database_url file, or set DATABASE_URL env var."
        )

    # Handle Supabase URLs that use postgres:// instead of postgresql://
    if url.startswith('postgres://'):
        url = url.replace('postgres://', 'postgresql://', 1)

    return url


def migrate_table(source_session, dest_session, table_name: str, dry_run: bool = False) -> int:
    """
    Migrate a single table from source to destination.

    :param source_session: SQLAlchemy session for source (SQLite)
    :param dest_session: SQLAlchemy session for destination (PostgreSQL)
    :param table_name: Name of the table to migrate
    :param dry_run: If True, don't actually write to destination
    :return: Number of rows migrated
    """
    # Get all rows from source
    result = source_session.execute(text(f"SELECT * FROM {table_name}"))
    rows = result.fetchall()
    columns = result.keys()

    if not rows:
        print(f"  {table_name}: 0 rows (empty)")
        return 0

    if dry_run:
        print(f"  {table_name}: {len(rows)} rows (dry run)")
        return len(rows)

    # Build INSERT statement with column names
    col_names = ", ".join(columns)
    placeholders = ", ".join([f":{col}" for col in columns])
    insert_sql = text(f"INSERT INTO {table_name} ({col_names}) VALUES ({placeholders})")

    # Insert rows
    for row in rows:
        row_dict = dict(zip(columns, row))
        dest_session.execute(insert_sql, row_dict)

    print(f"  {table_name}: {len(rows)} rows migrated")
    return len(rows)


def reset_sequences(dest_session, table_name: str, id_column: str = 'id'):
    """
    Reset PostgreSQL sequence to max ID value after migration.

    :param dest_session: SQLAlchemy session for destination
    :param table_name: Name of the table
    :param id_column: Name of the ID column (default: 'id')
    """
    # Get max ID
    result = dest_session.execute(text(f"SELECT MAX({id_column}) FROM {table_name}"))
    max_id = result.scalar()

    if max_id is not None:
        # Reset sequence to max_id + 1
        seq_name = f"{table_name}_{id_column}_seq"
        dest_session.execute(text(f"SELECT setval('{seq_name}', {max_id}, true)"))


def main():
    parser = argparse.ArgumentParser(
        description='Migrate Atacama database from SQLite to PostgreSQL.',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('--url', help='PostgreSQL connection URL')
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be migrated without writing')
    parser.add_argument('--skip-create-tables', action='store_true',
                       help='Skip table creation (tables already exist)')

    args = parser.parse_args()

    # Initialize constants (for paths)
    constants.init_production()

    # Get database URLs
    sqlite_url = f'sqlite:///{constants._PROD_DB_PATH}'
    postgres_url = get_postgres_url(args.url)

    print(f"Source: {sqlite_url}")
    print(f"Destination: {postgres_url[:50]}..." if len(postgres_url) > 50 else f"Destination: {postgres_url}")
    print()

    # Create engines
    source_engine = create_engine(sqlite_url)
    dest_engine = create_engine(postgres_url, pool_pre_ping=True)

    # Create tables in destination if needed
    if not args.skip_create_tables and not args.dry_run:
        print("Creating tables in destination database...")
        from models import Base
        Base.metadata.create_all(dest_engine)
        print("Tables created.")
        print()

    # Create sessions
    SourceSession = sessionmaker(bind=source_engine)
    DestSession = sessionmaker(bind=dest_engine)

    source_session = SourceSession()
    dest_session = DestSession()

    try:
        print("Migrating data...")

        # Migration order matters due to foreign key constraints
        # 1. Users first (no dependencies)
        # 2. Messages (depends on users)
        # 3. User tokens (depends on users)
        # 4. Emails, Articles, Quotes, ReactWidgets (depend on messages)
        # 5. Widget versions (depends on react_widgets)
        # 6. Email-quotes association (depends on emails and quotes)

        tables = [
            'users',
            'messages',
            'user_tokens',
            'emails',
            'articles',
            'quotes',
            'react_widgets',
            'widget_versions',
            'email_quotes',
        ]

        total_rows = 0
        for table in tables:
            try:
                rows = migrate_table(source_session, dest_session, table, args.dry_run)
                total_rows += rows
            except Exception as e:
                print(f"  {table}: ERROR - {e}")
                if not args.dry_run:
                    dest_session.rollback()
                    raise

        if not args.dry_run:
            # Reset sequences for tables with auto-increment IDs
            print()
            print("Resetting PostgreSQL sequences...")
            for table in ['users', 'messages', 'user_tokens', 'widget_versions']:
                try:
                    reset_sequences(dest_session, table)
                    print(f"  {table}_id_seq: reset")
                except Exception as e:
                    print(f"  {table}_id_seq: skipped ({e})")

            dest_session.commit()
            print()
            print(f"Migration complete! {total_rows} total rows migrated.")
        else:
            print()
            print(f"Dry run complete. {total_rows} total rows would be migrated.")

    except Exception as e:
        print(f"Migration failed: {e}")
        dest_session.rollback()
        return 1
    finally:
        source_session.close()
        dest_session.close()

    return 0


if __name__ == '__main__':
    sys.exit(main())
