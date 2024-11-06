import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from CiviCodeAPI.main import app
from CiviCodeAPI.database import Base, get_db
from CiviCodeAPI.models import Inspection

# Create a test database
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Override the get_db dependency to use the test database
def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

# Create the test database tables
Base.metadata.create_all(bind=engine)

client = TestClient(app)

@pytest.fixture(scope="module")
def test_client():
    yield client

def test_create_inspection(test_client):
    response = test_client.post(
        "/inspections/",
        json={
            "source": "Routine",
            "status": "Pending",
            "address_id": 1,
            "description": "Test inspection",
            "scheduled_datetime": "2023-10-01T10:00:00"
        }
    )
    assert response.status_code == 200
    # Add more assertions if needed
