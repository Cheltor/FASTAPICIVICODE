from fastapi import APIRouter, HTTPException, Depends, status, Form
from sqlalchemy.orm import Session
from typing import List, Optional
from database import get_db
from models import Notification, Inspection, User
from schemas import NotificationCreate, NotificationResponse
from fastapi.security import OAuth2PasswordBearer
import jwt
from email_service import send_notification_email
from email_service import EMAIL_ENABLED, SENDGRID_API_KEY, SENDGRID_FROM_EMAIL
from pydantic import BaseModel
import os

# Use the same auth settings as users
SECRET_KEY = "trpdds2020"
ALGORITHM = "HS256"
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login")

def _get_current_user_id(token: str = Depends(oauth2_scheme)) -> int:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return int(payload.get("sub"))
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

router = APIRouter()

@router.get("/notifications", response_model=List[NotificationResponse])
def list_notifications(db: Session = Depends(get_db), current_user_id: int = Depends(_get_current_user_id)):
    notifications = (
        db.query(Notification)
        .filter(Notification.user_id == current_user_id)
        .order_by(Notification.created_at.desc())
        .all()
    )
    return notifications

@router.post("/notifications", response_model=NotificationResponse, status_code=status.HTTP_201_CREATED)
def create_notification(payload: NotificationCreate, db: Session = Depends(get_db), current_user_id: int = Depends(_get_current_user_id)):
    # basic validation: inspection_id is optional now; comment_id is optional as well
    if payload.inspection_id:
        inspection = db.query(Inspection).filter(Inspection.id == payload.inspection_id).first()
        if not inspection:
            raise HTTPException(status_code=404, detail="Inspection not found")
    user = db.query(User).filter(User.id == payload.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    # Only allow creating a notification for oneself (or elevate later with admin roles)
    if payload.user_id != current_user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot create notifications for other users")

    notif = Notification(
        title=payload.title,
        body=payload.body,
        inspection_id=payload.inspection_id,
        comment_id=getattr(payload, 'comment_id', None),
        user_id=payload.user_id,
        read=payload.read or False,
    )
    db.add(notif)
    db.commit()
    db.refresh(notif)
    # Email: send to recipient; allow override via TEST_EMAIL_USER_ID
    try:
        import os
        override_id = os.getenv("TEST_EMAIL_USER_ID")
        target_user_id = int(override_id) if override_id else int(payload.user_id)
        target_user = db.query(User).filter(User.id == target_user_id).first()
        if target_user and target_user.email:
            subj = payload.title or "Notification"
            send_notification_email(subject=subj, body=payload.body or "", to_email=target_user.email, inspection_id=payload.inspection_id)
    except Exception:
        # ignore email errors
        pass
    return notif

@router.get("/notifications/{notification_id}", response_model=NotificationResponse)
def get_notification(notification_id: int, db: Session = Depends(get_db), current_user_id: int = Depends(_get_current_user_id)):
    notif = db.query(Notification).filter(Notification.id == notification_id, Notification.user_id == current_user_id).first()
    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found")
    return notif

@router.patch("/notifications/{notification_id}/read", response_model=NotificationResponse)
def mark_notification_read(notification_id: int, db: Session = Depends(get_db), current_user_id: int = Depends(_get_current_user_id)):
    notif = db.query(Notification).filter(Notification.id == notification_id, Notification.user_id == current_user_id).first()
    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found")
    notif.read = True
    db.commit()
    db.refresh(notif)
    return notif

@router.delete("/notifications/{notification_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_notification(notification_id: int, db: Session = Depends(get_db), current_user_id: int = Depends(_get_current_user_id)):
    notif = db.query(Notification).filter(Notification.id == notification_id, Notification.user_id == current_user_id).first()
    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found")
    db.delete(notif)
    db.commit()
    return None

@router.patch("/notifications/read-all", response_model=int)
def mark_all_notifications_read(db: Session = Depends(get_db), current_user_id: int = Depends(_get_current_user_id)):
    updated = (
        db.query(Notification)
        .filter(Notification.user_id == current_user_id, Notification.read == False)
        .update({Notification.read: True}, synchronize_session=False)
    )
    db.commit()
    return updated

# Test email endpoint for admins or any authenticated user; routes to override if set
class TestEmailRequest(BaseModel):
    subject: Optional[str] = "Test notification email"
    body: Optional[str] = "This is a test notification email."
    inspection_id: Optional[int] = None

@router.post("/notifications/test-email")
def send_test_email(payload: TestEmailRequest, db: Session = Depends(get_db), current_user_id: int = Depends(_get_current_user_id)):
    # Determine target user: TEST_EMAIL_USER_ID override or current user
    override_id = os.getenv("TEST_EMAIL_USER_ID")
    target_id = int(override_id) if override_id else int(current_user_id)
    target_user = db.query(User).filter(User.id == target_id).first()
    if not target_user or not target_user.email:
        raise HTTPException(status_code=400, detail="No valid recipient email available for test.")

    # Find the most recent notification across all users and resend it
    notif = (
        db.query(Notification)
        .order_by(Notification.created_at.desc())
        .first()
    )
    if not notif:
        raise HTTPException(status_code=404, detail="No notifications found to send for this user.")

    subject = notif.title or "Notification"
    body = notif.body or ""
    sent = send_notification_email(
        subject=subject,
        body=body,
        to_email=target_user.email,
        inspection_id=getattr(notif, "inspection_id", None),
    )
    return {
        "ok": True,
        "email_sent": bool(sent),
        "notification_id": notif.id,
        "to_user_id": target_user.id,
        "email_config": {
            "enabled": bool(EMAIL_ENABLED),
            "has_api_key": bool(SENDGRID_API_KEY),
            "from_email": SENDGRID_FROM_EMAIL,
        },
    }