import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker, with_loader_criteria

from CiviCodeAPI.models import Base, SoftDeleteMixin

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


@event.listens_for(Session, "before_flush")
def _apply_soft_delete(session, flush_context, instances):
    """Convert ORM deletes into soft deletes."""

    for instance in list(session.deleted):
        if isinstance(instance, SoftDeleteMixin):
            session.deleted.discard(instance)
            instance.mark_deleted()
            session.add(instance)


def _soft_delete_models():
    return [
        mapper.class_
        for mapper in Base.registry.mappers
        if issubclass(mapper.class_, SoftDeleteMixin)
    ]


@event.listens_for(Session, "do_orm_execute")
def _filter_soft_deleted(execute_state):
    if not execute_state.is_select:
        return

    if execute_state.execution_options.get("include_deleted"):
        return

    for model in _soft_delete_models():
        execute_state.statement = execute_state.statement.options(
            with_loader_criteria(
                model,
                lambda cls: cls.deleted_at.is_(None),
                include_aliases=True,
            )
        )


# Dependency for getting the database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
