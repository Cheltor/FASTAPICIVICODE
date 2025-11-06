import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.inspection import inspect

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

DEFAULT_SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
SQLALCHEMY_DATABASE_URL = os.getenv("TEST_DATABASE_URL") or DEFAULT_SQLALCHEMY_DATABASE_URL

# Ensure the application itself uses the test database instead of the production default.
os.environ.setdefault("DATABASE_URL", SQLALCHEMY_DATABASE_URL)

from CiviCodeAPI.main import app
from CiviCodeAPI.database import Base, get_db


def _create_engine(url: str):
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, pool_pre_ping=True, connect_args=connect_args)


engine = _create_engine(SQLALCHEMY_DATABASE_URL)


class _TestingSession(Session):
    pass


TestingSessionLocal = sessionmaker(
    autocommit=False, autoflush=False, bind=engine, class_=_TestingSession
)


def _next_sqlite_pk(connection, pk_column):
    stmt = select(func.max(pk_column))
    current_max = connection.execute(stmt).scalar()
    return (current_max or 0) + 1


def assign_sqlite_pk(session, instance) -> None:
    """Assign an auto-incrementing primary key when using SQLite."""

    mapper = inspect(instance.__class__)
    pk_columns = mapper.primary_key
    if len(pk_columns) != 1:
        return

    pk_column = pk_columns[0]
    pk_name = pk_column.name
    if getattr(instance, pk_name) is not None:
        return

    bind = session.get_bind(mapper=mapper)
    if bind is None or bind.dialect.name != "sqlite":
        return

    current_max = session.execute(select(func.max(pk_column))).scalar()
    setattr(instance, pk_name, (current_max or 0) + 1)


@event.listens_for(Base, "before_insert", propagate=True)
def _ensure_sqlite_primary_keys(mapper, connection, target):
    if connection.dialect.name != "sqlite":
        return

    pk_columns = mapper.primary_key
    if len(pk_columns) != 1:
        return

    pk_column = pk_columns[0]
    pk_name = pk_column.name
    if getattr(target, pk_name) is not None:
        return

    next_value = _next_sqlite_pk(connection, pk_column)
    setattr(target, pk_name, next_value)

try:
    with engine.begin() as connection:
        Base.metadata.drop_all(bind=connection)
        Base.metadata.create_all(bind=connection)
except OperationalError as exc:
    raise RuntimeError(
        "Unable to initialize the database schema for tests. "
        "Set TEST_DATABASE_URL to a reachable database URL or ensure SQLite is available."
    ) from exc


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(scope="module")
def test_client():
    with TestClient(app) as client:
        yield client
