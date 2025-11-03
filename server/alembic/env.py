# server/alembic/env.py
from __future__ import annotations

import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

# Ensure "server" is importable
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))  # /app/server/alembic
SERVER_DIR = os.path.dirname(CURRENT_DIR)                 # /app/server
if SERVER_DIR not in sys.path:
    sys.path.insert(0, SERVER_DIR)

from server.models import Base  # noqa: E402

config = context.config

# Logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_url() -> str:
    # Prefer env var; fall back to alembic.ini
    env_url = os.getenv("DATABASE_URL")
    if env_url:
        return env_url
    return config.get_main_option("sqlalchemy.url")


def run_migrations_offline() -> None:
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    url = get_url()
    engine = create_engine(url, poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
