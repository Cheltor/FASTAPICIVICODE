import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
from models import Base

# Load environment variables from .env for local dev
load_dotenv()


def _database_url() -> str:
    """Resolve the database URL from environment with Heroku-friendly defaults."""
    url = (
        os.getenv("DATABASE_URL")
        or os.getenv("HEROKU_DATABASE_URL")
        or "postgresql://rchelton:password@localhost:5433/codeenforcement_development"
    )
    # Normalize Heroku's postgres:// to SQLAlchemy's expected scheme
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg2://", 1)
    # Force SSL on Heroku dynos if not specified
    if os.getenv("DYNO") and "sslmode=" not in url:
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}sslmode=require"
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
