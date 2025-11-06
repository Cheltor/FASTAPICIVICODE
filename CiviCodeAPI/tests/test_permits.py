from CiviCodeAPI.models import Address, Inspection, Permit
from CiviCodeAPI.tests.conftest import TestingSessionLocal, assign_sqlite_pk


def test_put_updates_permit_and_returns_combadd(test_client):
    db = TestingSessionLocal()
    try:
        # Create address and inspection
        addr = Address(combadd="123 MAIN ST")
        assign_sqlite_pk(db, addr)
        db.add(addr)
        db.commit()
        db.refresh(addr)

        insp = Inspection(address_id=addr.id)
        assign_sqlite_pk(db, insp)
        db.add(insp)
        db.commit()
        db.refresh(insp)

        permit = Permit(inspection_id=insp.id, permit_type="Old", permit_number="OLD-1", paid=False)
        assign_sqlite_pk(db, permit)
        db.add(permit)
        db.commit()
        db.refresh(permit)

        # Perform PUT to update permit
        payload = {"permit_type": "Building", "permit_number": "BP-999", "paid": True}
        res = test_client.put(f"/permits/{permit.id}", json=payload)
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["permit_type"] == "Building"
        assert data["permit_number"] == "BP-999"
        assert data["paid"] is True
        # Ensure combadd and address_id are present
        assert data.get("combadd") == "123 MAIN ST"
        assert data.get("address_id") == addr.id
    finally:
        db.close()
