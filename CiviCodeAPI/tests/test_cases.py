import pytest
from fastapi.testclient import TestClient
from CiviCodeAPI.main import app

client = TestClient(app)

def test_create_case():
    response = client.post("/cases/", json={"address_id": 1, "status": "Received"})
    assert response.status_code == 200
    assert response.json()["status"] == "Received"

def test_create_violation_with_case():
    response = client.post("/violations/", json={"address_id": 1, "user_id": 1, "status": 0, "case_id": 1})
    assert response.status_code == 200
    assert response.json()["case_id"] == 1

def test_create_violation_without_case():
    response = client.post("/violations/", json={"address_id": 1, "user_id": 1, "status": 0})
    assert response.status_code == 200
    assert response.json()["case_id"] is not None
