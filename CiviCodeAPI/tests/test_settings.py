import jwt
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base, User, AppSetting, AppSettingAudit
from main import app
from database import get_db
from datetime import datetime, timedelta

SECRET_KEY = "trpdds2020"
ALGORITHM = "HS256"

TEST_SQLITE_URL = "sqlite:///:memory:"
engine = create_engine(TEST_SQLITE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base.metadata.create_all(bind=engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


def create_user(db, email: str, role: int = 0):
    user = User(email=email, encrypted_password='test', role=role)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_token_for_user(user_id: int):
    payload = {"sub": str(user_id), "exp": datetime.utcnow() + timedelta(hours=1)}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def test_get_default_chat_setting():
    resp = client.get('/settings/chat')
    assert resp.status_code == 200
    data = resp.json()
    assert 'enabled' in data


def test_patch_chat_setting_admin():
    # use internal DB session for setup
    db = TestingSessionLocal()
    try:
        admin = create_user(db, 'admin@example.com', role=3)
        token = get_token_for_user(admin.id)
        headers = {'Authorization': f'Bearer {token}'}

        resp = client.patch('/settings/chat', json={'enabled': False}, headers=headers)
        assert resp.status_code == 200
        assert resp.json().get('enabled') is False

        # verify in DB
        setting = db.query(AppSetting).filter(AppSetting.key == 'chat_enabled').first()
        assert setting is not None
        assert setting.value == 'false'

        audit = db.query(AppSettingAudit).filter(AppSettingAudit.key == 'chat_enabled').order_by(AppSettingAudit.changed_at.desc()).first()
        assert audit is not None
        assert audit.changed_by == admin.id
    finally:
        db.close()


def test_patch_chat_setting_non_admin_forbidden():
    db = TestingSessionLocal()
    try:
        user = create_user(db, 'user@example.com', role=1)
        token = get_token_for_user(user.id)
        headers = {'Authorization': f'Bearer {token}'}

        resp = client.patch('/settings/chat', json={'enabled': True}, headers=headers)
        assert resp.status_code == 403
    finally:
        db.close()
