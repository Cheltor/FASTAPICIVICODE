import os
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
from models import Base

def _load_env() -> None:
    """Load environment for local development.

    - Prefer .env.development in the FastAPI project root.
    - Fallback to .env if dev file is missing.
    - Do nothing on Heroku dynos (env vars provided by platform).
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
    """Resolve the database URL from the environment."""
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
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
