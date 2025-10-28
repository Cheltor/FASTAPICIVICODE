from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from database import get_db
from models import AppSetting, User, AppSettingAudit, ChatLog
import jwt
from fastapi.security import OAuth2PasswordBearer
from fastapi.responses import StreamingResponse
import json
from settings_broadcast import broadcaster
from typing import Optional
from datetime import datetime
from sqlalchemy.orm import joinedload
import asyncio

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
        """
        SSE generator that yields broadcaster events and sends a heartbeat comment
        at regular intervals so the connection is not considered idle by Heroku.
        """
        sub = broadcaster.subscribe()
        HEARTBEAT_INTERVAL = 25  # seconds; must be < Heroku 55s idle timeout
        try:
            while True:
                try:
                    # Wait for next broadcast item, but timeout so we can heartbeat
                    item = await asyncio.wait_for(sub.__anext__(), timeout=HEARTBEAT_INTERVAL)
                    yield f"data: {json.dumps(item)}\n\n"
                except asyncio.TimeoutError:
                    # SSE comment is ignored by clients but keeps the connection active
                    yield ": keep-alive\n\n"
                except StopAsyncIteration:
                    break
        finally:
            # close subscription if publisher supports aclose()
            close = getattr(sub, "aclose", None)
            if callable(close):
                try:
                    await close()
                except Exception:
                    pass

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


# Admin-only endpoint to fetch recent chat logs
@router.get("/settings/chat/logs")
def get_chat_logs(
    limit: int = 100,
    offset: int = 0,
    user_id: Optional[int] = None,
    user_email: Optional[str] = None,
    thread_id: Optional[str] = None,
    q: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(_get_current_user),
):
    # only admins may read logs
    if current_user.role != 3:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")

    query = db.query(ChatLog).options(joinedload(ChatLog.user))

    # Support filtering by numeric user_id OR by user_email (partial match)
    if user_id is not None:
        query = query.filter(ChatLog.user_id == user_id)
    if user_email:
        # find matching users (partial case-insensitive match)
        from models import User as UserModel
        matched = db.query(UserModel.id).filter(UserModel.email.ilike(f"%{user_email}%")).all()
        matched_ids = [m[0] for m in matched]
        if matched_ids:
            query = query.filter(ChatLog.user_id.in_(matched_ids))
        else:
            # No users match => empty result
            return {"total": 0, "limit": limit, "offset": offset, "items": []}
    if thread_id:
        query = query.filter(ChatLog.thread_id == thread_id)
    if start_date:
        query = query.filter(ChatLog.created_at >= start_date)
    if end_date:
        query = query.filter(ChatLog.created_at <= end_date)
    if q:
        pattern = f"%{q}%"
        # search both user_message and assistant_reply
        query = query.filter(
            (ChatLog.user_message.ilike(pattern)) | (ChatLog.assistant_reply.ilike(pattern))
        )

    total = query.count()
    logs = query.order_by(ChatLog.created_at.desc()).offset(offset).limit(limit).all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": [
            {
                "id": l.id,
                "user_id": l.user_id,
                "user_email": l.user.email if l.user else None,
                "thread_id": l.thread_id,
                "user_message": l.user_message,
                "assistant_reply": l.assistant_reply,
                "created_at": l.created_at,
            }
            for l in logs
        ],
    }
