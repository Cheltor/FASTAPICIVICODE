from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
import jwt
from typing import List

from database import get_db
from models import PushSubscription
from schemas import (
    PushSubscriptionCreate,
    PushSubscriptionDelete,
    PushSubscriptionResponse,
)

SECRET_KEY = "trpdds2020"
ALGORITHM = "HS256"
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login")


def _get_current_user_id(token: str = Depends(oauth2_scheme)) -> int:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return int(payload.get("sub"))
    except Exception as exc:  # pragma: no cover - defensive only
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc


router = APIRouter(prefix="/push-subscriptions", tags=["push subscriptions"])


@router.get("", response_model=List[PushSubscriptionResponse])
def list_push_subscriptions(
    db: Session = Depends(get_db),
    current_user_id: int = Depends(_get_current_user_id),
):
    return (
        db.query(PushSubscription)
        .filter(PushSubscription.user_id == current_user_id)
        .order_by(PushSubscription.created_at.desc())
        .all()
    )


@router.post("", response_model=PushSubscriptionResponse, status_code=status.HTTP_201_CREATED)
def upsert_push_subscription(
    payload: PushSubscriptionCreate,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(_get_current_user_id),
):
    if not payload.keys or not payload.keys.p256dh or not payload.keys.auth:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing subscription keys")

    subscription = (
        db.query(PushSubscription)
        .filter(PushSubscription.endpoint == payload.endpoint)
        .first()
    )

    if subscription:
        subscription.user_id = current_user_id
        subscription.p256dh = payload.keys.p256dh
        subscription.auth = payload.keys.auth
        subscription.expiration_time = payload.expiration_time
        subscription.user_agent = payload.user_agent
    else:
        subscription = PushSubscription(
            user_id=current_user_id,
            endpoint=payload.endpoint,
            p256dh=payload.keys.p256dh,
            auth=payload.keys.auth,
            expiration_time=payload.expiration_time,
            user_agent=payload.user_agent,
        )
        db.add(subscription)

    db.commit()
    db.refresh(subscription)
    return subscription


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
def delete_push_subscription(
    payload: PushSubscriptionDelete,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(_get_current_user_id),
):
    if not payload.endpoint:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing endpoint")

    subscription = (
        db.query(PushSubscription)
        .filter(PushSubscription.user_id == current_user_id, PushSubscription.endpoint == payload.endpoint)
        .first()
    )
    if subscription:
        db.delete(subscription)
        db.commit()
    return None
