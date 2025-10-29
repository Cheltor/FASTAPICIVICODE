from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from CiviCodeAPI.main import app
from CiviCodeAPI.database import get_db
from CiviCodeAPI.models import Base, Address, Inspection, Permit

# Use an in-memory SQLite database for tests
TEST_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


client = TestClient(app)


def setup_module(module):
    # Create tables
    Base.metadata.create_all(bind=engine)


def teardown_module(module):
    Base.metadata.drop_all(bind=engine)


def test_put_updates_permit_and_returns_combadd():
    db = TestingSessionLocal()
    # Create address and inspection
    addr = Address(combadd="123 MAIN ST")
    db.add(addr)
    db.commit()
    db.refresh(addr)

    insp = Inspection(address_id=addr.id)
    db.add(insp)
    db.commit()
    db.refresh(insp)

    permit = Permit(inspection_id=insp.id, permit_type="Old", permit_number="OLD-1", paid=False)
    db.add(permit)
    db.commit()
    db.refresh(permit)

    # Perform PUT to update permit
    payload = {"permit_type": "Building", "permit_number": "BP-999", "paid": True}
    res = client.put(f"/permits/{permit.id}", json=payload)
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["permit_type"] == "Building"
    assert data["permit_number"] == "BP-999"
    assert data["paid"] is True
    # Ensure combadd and address_id are present
    assert data.get("combadd") == "123 MAIN ST"
    assert data.get("address_id") == addr.id

    db.close()
