from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from database import get_db
from models import AppSetting, User, AppSettingAudit, ChatLog
import jwt
from fastapi.security import OAuth2PasswordBearer
from fastapi.responses import StreamingResponse
import logging
import json
from settings_broadcast import broadcaster
from typing import Optional
from datetime import datetime
from sqlalchemy.orm import joinedload
import asyncio
from contextlib import suppress

router = APIRouter()

SECRET_KEY = "trpdds2020"
ALGORITHM = "HS256"
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login")

class ChatSettingResponse(BaseModel):
    enabled: bool

class ChatSettingUpdate(BaseModel):
    enabled: bool


def _get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    """
    Get the current authenticated user.

    Args:
        token (str): OAuth2 token.
        db (Session): The database session.

    Returns:
        User: The user object.

    Raises:
        HTTPException: If token invalid or user not found.
    """
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
    """
    Get the current chat enablement setting.

    Args:
        db (Session): The database session.

    Returns:
        ChatSettingResponse: The setting state.
    """
    setting = db.query(AppSetting).filter(AppSetting.key == "chat_enabled").first()
    if not setting:
        # default to enabled
        return {"enabled": True}
    return {"enabled": setting.value.lower() == "true"}


@router.get('/settings/stream')
def settings_stream():
    """
    SSE endpoint for streaming settings updates.

    Returns:
        StreamingResponse: Server-Sent Events stream.
    """
    async def event_generator():
        """
        SSE generator that yields broadcaster events and sends a heartbeat comment
        at regular intervals so the connection is not considered idle by Heroku.
        """
        sub = broadcaster.subscribe()
        HEARTBEAT_INTERVAL = 25  # seconds; must be < Heroku 55s idle timeout
        event_task = asyncio.create_task(sub.__anext__())
        heartbeat_task = asyncio.create_task(asyncio.sleep(HEARTBEAT_INTERVAL))
        try:
            while True:
                done, _ = await asyncio.wait(
                    {event_task, heartbeat_task},
                    return_when=asyncio.FIRST_COMPLETED,
                )

                if event_task in done:
                    try:
                        item = event_task.result()
                    except StopAsyncIteration:
                        return
                    yield f"data: {json.dumps(item)}\n\n"
                    event_task = asyncio.create_task(sub.__anext__())

                if heartbeat_task in done:
                    # SSE comment is ignored by clients but keeps the connection active
                    yield ": keep-alive\n\n"
                    heartbeat_task = asyncio.create_task(asyncio.sleep(HEARTBEAT_INTERVAL))
        except Exception:
            logging.exception("Exception in settings_stream event_generator")
            raise
        finally:
            for task in (event_task, heartbeat_task):
                task.cancel()
            with suppress(asyncio.CancelledError, StopAsyncIteration):
                await event_task
            with suppress(asyncio.CancelledError):
                await heartbeat_task
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
    """
    Update the chat enablement setting.

    Args:
        payload (ChatSettingUpdate): New setting value.
        db (Session): The database session.
        current_user (User): The authenticated user (admin only).

    Returns:
        ChatSettingResponse: The updated setting.

    Raises:
        HTTPException: If permission denied.
    """
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
    """
    Fetch chat logs with filtering (admin only).

    Args:
        limit (int): Max logs.
        offset (int): Pagination offset.
        user_id (int, optional): Filter by user ID.
        user_email (str, optional): Filter by user email.
        thread_id (str, optional): Filter by thread ID.
        q (str, optional): Search query.
        start_date (datetime, optional): Start date filter.
        end_date (datetime, optional): End date filter.
        db (Session): The database session.
        current_user (User): The authenticated user.

    Returns:
        dict: List of chat logs and metadata.

    Raises:
        HTTPException: If permission denied.
    """
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


# Image Analysis Settings & Logs

@router.get("/settings/image-analysis", response_model=ChatSettingResponse)
def get_image_analysis_setting(db: Session = Depends(get_db)):
    """
    Get the image analysis enablement setting.

    Args:
        db (Session): The database session.

    Returns:
        ChatSettingResponse: The setting state.
    """
    setting = db.query(AppSetting).filter(AppSetting.key == "image_analysis_enabled").first()
    if not setting:
        # default to enabled
        return {"enabled": True}
    return {"enabled": setting.value.lower() == "true"}

@router.patch("/settings/image-analysis", response_model=ChatSettingResponse)
def set_image_analysis_setting(payload: ChatSettingUpdate, db: Session = Depends(get_db), current_user: User = Depends(_get_current_user)):
    """
    Update the image analysis enablement setting.

    Args:
        payload (ChatSettingUpdate): New setting value.
        db (Session): The database session.
        current_user (User): The authenticated user (admin only).

    Returns:
        ChatSettingResponse: The updated setting.

    Raises:
        HTTPException: If permission denied.
    """
    # Only allow admins (role == 3)
    if current_user.role != 3:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")

    setting = db.query(AppSetting).filter(AppSetting.key == "image_analysis_enabled").first()
    value_str = "true" if payload.enabled else "false"
    
    old = setting.value if setting else None
    if setting:
        setting.value = value_str
    else:
        setting = AppSetting(key="image_analysis_enabled", value=value_str)
        db.add(setting)

    # add audit row
    audit = AppSettingAudit(key="image_analysis_enabled", old_value=old, new_value=value_str, changed_by=current_user.id)
    db.add(audit)
    db.commit()

    # notify subscribers
    try:
        broadcaster.publish_nowait({"key": "image_analysis_enabled", "enabled": value_str == 'true'})
    except Exception:
        pass
    return {"enabled": payload.enabled}

@router.get("/settings/image-analysis/logs")
def get_image_analysis_logs(
    limit: int = 100,
    offset: int = 0,
    user_id: Optional[int] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(_get_current_user),
):
    """
    Fetch image analysis logs (admin only).

    Args:
        limit (int): Max logs.
        offset (int): Pagination offset.
        user_id (int, optional): Filter by user ID.
        start_date (datetime, optional): Start date filter.
        end_date (datetime, optional): End date filter.
        db (Session): The database session.
        current_user (User): The authenticated user.

    Returns:
        dict: List of logs and metadata.

    Raises:
        HTTPException: If permission denied.
    """
    # only admins may read logs
    if current_user.role != 3:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")

    from models import ImageAnalysisLog, ActiveStorageAttachment, ActiveStorageBlob
    from azure.storage.blob import generate_blob_sas, BlobSasPermissions
    import storage

    query = db.query(ImageAnalysisLog).options(joinedload(ImageAnalysisLog.user))

    if user_id is not None:
        query = query.filter(ImageAnalysisLog.user_id == user_id)
    if start_date:
        query = query.filter(ImageAnalysisLog.created_at >= start_date)
    if end_date:
        query = query.filter(ImageAnalysisLog.created_at <= end_date)

    total = query.count()
    logs = query.order_by(ImageAnalysisLog.created_at.desc()).offset(offset).limit(limit).all()

    # For each log, fetch associated images and generate SAS URLs
    results = []
    for l in logs:
        # Fetch attachments
        attachments = db.query(ActiveStorageAttachment).filter(
            ActiveStorageAttachment.record_type == 'ImageAnalysisLog',
            ActiveStorageAttachment.record_id == l.id
        ).all()
        
        images = []
        for att in attachments:
            blob = db.query(ActiveStorageBlob).filter(ActiveStorageBlob.id == att.blob_id).first()
            if blob:
                try:
                    sas_token = generate_blob_sas(
                        account_name=storage.account_name,
                        container_name=storage.CONTAINER_NAME,
                        blob_name=blob.key,
                        account_key=storage.account_key,
                        permission=BlobSasPermissions(read=True),
                        start=datetime.utcnow() - timedelta(minutes=5),
                        expiry=datetime.utcnow() + timedelta(hours=1),
                    )
                    url = f"https://{storage.account_name}.blob.core.windows.net/{storage.CONTAINER_NAME}/{blob.key}?{sas_token}"
                    images.append({"url": url, "filename": blob.filename, "content_type": blob.content_type})
                except Exception as e:
                    logging.error(f"Error generating SAS for blob {blob.key}: {e}")

        results.append({
            "id": l.id,
            "user_id": l.user_id,
            "user_email": l.user.email if l.user else None,
            "image_count": l.image_count,
            "result": l.result,
            "status": l.status,
            "created_at": l.created_at,
            "images": images
        })

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": results,
    }
