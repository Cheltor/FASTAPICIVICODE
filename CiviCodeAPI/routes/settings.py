from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from database import get_db
from models import AppSetting, User, AppSettingAudit
import jwt
from fastapi.security import OAuth2PasswordBearer
from fastapi.responses import StreamingResponse
import json
from settings_broadcast import broadcaster

router = APIRouter()

SECRET_KEY = "trpdds2020"
ALGORITHM = "HS256"
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login")

class ChatSettingResponse(BaseModel):
    enabled: bool

class ChatSettingUpdate(BaseModel):
    enabled: bool


def _get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = int(payload.get("sub"))
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


@router.get("/settings/chat", response_model=ChatSettingResponse)
def get_chat_setting(db: Session = Depends(get_db)):
    setting = db.query(AppSetting).filter(AppSetting.key == "chat_enabled").first()
    if not setting:
        # default to enabled
        return {"enabled": True}
    return {"enabled": setting.value.lower() == "true"}


@router.get('/settings/stream')
def settings_stream():
    async def event_generator():
        async for item in broadcaster.subscribe():
            yield f"data: {json.dumps(item)}\n\n"

    return StreamingResponse(event_generator(), media_type='text/event-stream')


@router.patch("/settings/chat", response_model=ChatSettingResponse)
def set_chat_setting(payload: ChatSettingUpdate, db: Session = Depends(get_db), current_user: User = Depends(_get_current_user)):
    # Only allow admins (role == 3)
    if current_user.role != 3:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")

    setting = db.query(AppSetting).filter(AppSetting.key == "chat_enabled").first()
    value_str = "true" if payload.enabled else "false"
    from datetime import datetime

    old = setting.value if setting else None
    if setting:
        setting.value = value_str
    else:
        setting = AppSetting(key="chat_enabled", value=value_str)
        db.add(setting)

    # add audit row
    audit = AppSettingAudit(key="chat_enabled", old_value=old, new_value=value_str, changed_by=current_user.id)
    db.add(audit)
    db.commit()

    # notify subscribers
    try:
        broadcaster.publish_nowait({"key": "chat_enabled", "enabled": value_str == 'true'})
    except Exception:
        pass
    return {"enabled": payload.enabled}
