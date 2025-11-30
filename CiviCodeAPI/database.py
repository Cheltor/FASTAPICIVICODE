"""
Database configuration and session management.

This module handles database connection, environment variable loading for database
credentials, and provides the session dependency for FastAPI path operations.
"""

import os
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
from models import Base

def _load_env() -> None:
    """
    Load environment variables for local development.

    Prefer `.env.development` in the FastAPI project root. Fallback to `.env`
    if the development file is missing. Does nothing on Heroku dynos where
    environment variables are provided by the platform.

    Returns:
        None
    """
    if os.getenv("DYNO"):
        return
    root = Path(__file__).resolve().parents[1]  # FastAPI directory
    dev_env = root / ".env.development"
    default_env = root / ".env"
    if dev_env.exists():
        load_dotenv(dev_env)
    elif default_env.exists():
        load_dotenv(default_env)


_load_env()


def _database_url() -> str:
    """
    Resolve the database URL from the environment.

    Returns:
        str: The database connection URL string. Normalizes `postgres://` to
        `postgresql://` for SQLAlchemy compatibility.
    """
    url = os.getenv("DATABASE_URL")
    if not url:
        # Fallback for local development if a .env file is not present.
        url = "postgresql://rchelton:password@localhost:5433/codeenforcement_development"

    # Normalize postgres:// scheme for SQLAlchemy compatibility.
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)

    return url


# Create the SQLAlchemy engine
engine = create_engine(_database_url())

# Create a configured "Session" class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# Dependency for getting the database session
def get_db():
    """
    Get a database session.

    This function is designed to be used as a FastAPI dependency. It yields a
    database session and ensures it is closed after the request is processed.

    Yields:
        sqlalchemy.orm.Session: A database session.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
