from CiviCodeAPI.models import User
from CiviCodeAPI.utils import hash_password, verify_password
from .conftest import TestingSessionLocal


def test_password_reset_flow(test_client):
    email = "forgot@example.com"

    # Prepare user in database
    session = TestingSessionLocal()
    try:
        session.query(User).filter(User.email == email).delete()
        user = User(email=email, encrypted_password=hash_password("InitialPass1"))
        session.add(user)
        session.commit()
    finally:
        session.close()

    # Request password reset
    response = test_client.post("/password/forgot", json={"email": email})
    assert response.status_code == 200

    # Token should now be stored for user
    session = TestingSessionLocal()
    try:
        user = session.query(User).filter(User.email == email).first()
        assert user is not None
        token = user.reset_password_token
        assert token
    finally:
        session.close()

    # Reset password using token
    response = test_client.post(
        "/password/reset",
        json={"token": token, "password": "NewSecurePass1"},
    )
    assert response.status_code == 200

    # Password should be updated and token cleared
    session = TestingSessionLocal()
    try:
        user = session.query(User).filter(User.email == email).first()
        assert user is not None
        assert user.reset_password_token is None
        assert user.reset_password_sent_at is None
        assert verify_password("NewSecurePass1", user.encrypted_password)
    finally:
        session.close()

