# migrations/env.py
from logging.config import fileConfig
import os
from pathlib import Path
import platform

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# Import your models to make metadata available
import sys
sys.path.append(str(Path(__file__).parent.parent / "src"))
from common.models import Base
import constants

# this is the Alembic Config object
config = context.config

# Set up logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set the database URL
db_url = f'sqlite:///{constants.DB_PATH}'
config.set_main_option('sqlalchemy.url', db_url)

# Add MetaData object from your models
target_metadata = Base.metadata

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
