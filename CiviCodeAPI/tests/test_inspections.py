from CiviCodeAPI.models import Address
from CiviCodeAPI.tests.conftest import TestingSessionLocal, assign_sqlite_pk


def test_create_inspection(test_client):
    session = TestingSessionLocal()
    try:
        address = Address(combadd="123 TEST ST")
        assign_sqlite_pk(session, address)
        session.add(address)
        session.commit()
        session.refresh(address)
        address_id = address.id
    finally:
        session.close()

    response = test_client.post(
        "/inspections/",
        data={
            "source": "Routine",
            "address_id": str(address_id),
            "description": "Test inspection",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["address_id"] == address_id
