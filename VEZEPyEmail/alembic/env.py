from __future__ import annotations
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from sqlalchemy.engine import Connection
from alembic import context
import os

from db.base import Base
from db import models  # noqa: F401 ensures models are imported

config = context.config

# Allow overriding DB URL via environment (and prefer sync driver for Alembic)
env_url = os.getenv("EMAIL_DB_URL")
if env_url:
    # Alembic uses sync engines; map sqlite+aiosqlite -> sqlite
    if env_url.startswith("sqlite+aiosqlite"):
        env_url = env_url.replace("sqlite+aiosqlite", "sqlite")
    config.set_main_option("sqlalchemy.url", env_url)

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    try:
        fileConfig(config.config_file_name)
    except Exception:
        # logging config optional
        pass

target_metadata = Base.metadata


def run_migrations_offline() -> None:
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
    connectable = engine_from_config(
        config.get_section(config.config_ini_section) or {},
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
