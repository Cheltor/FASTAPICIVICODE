from logging.config import fileConfig
import os
from pathlib import Path
from dotenv import load_dotenv

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# Import your models' Base class
from CiviCodeAPI.models import Base

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set target_metadata to the Base's metadata
target_metadata = Base.metadata


def _get_database_url() -> str:
    """Return DB URL from env (preferred) or alembic.ini, normalized for SQLAlchemy.

    - Prefer DATABASE_URL (Heroku) if present.
    - Normalize postgres:// to postgresql+psycopg2:// for SQLAlchemy/psycopg2.
    - On Heroku (DYNO set), ensure sslmode=require unless already specified.
    """
    # Prefer DATABASE_URL from environment (Heroku config var)
    # load env for local development (prefer .env.development)
    if not os.getenv("DYNO"):
        root = Path(__file__).resolve().parents[1]  # FastAPI project root
        dev = root / ".env.development"
        default = root / ".env"
        if dev.exists():
            load_dotenv(dev)
        elif default.exists():
            load_dotenv(default)

    url = os.getenv("DATABASE_URL") or context.config.get_main_option("sqlalchemy.url", "")
    # treat placeholder like empty
    if url.strip().endswith("://"):
        url = ""
    if not url:
        raise RuntimeError(
            "No database URL found. Set DATABASE_URL env var or sqlalchemy.url in alembic.ini"
        )

    # Normalize scheme for SQLAlchemy
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg2://", 1)

    # Ensure SSL on Heroku dynos if not already present
    if os.getenv("DYNO") and "sslmode=" not in url:
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}sslmode=require"

    return url

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = _get_database_url()
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
    # Build configuration dict and override URL from environment if provided
    configuration = config.get_section(config.config_ini_section, {}) or {}
    configuration["sqlalchemy.url"] = _get_database_url()

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
