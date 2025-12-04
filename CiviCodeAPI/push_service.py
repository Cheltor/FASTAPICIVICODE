import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, Iterable

from pywebpush import WebPushException, webpush
from sqlalchemy.orm import Session

from models import PushSubscription
from schemas import NotificationResponse

logger = logging.getLogger(__name__)

VAPID_PUBLIC_KEY = os.getenv("WEB_PUSH_VAPID_PUBLIC_KEY")
VAPID_PRIVATE_KEY = os.getenv("WEB_PUSH_VAPID_PRIVATE_KEY")
VAPID_CONTACT = os.getenv("WEB_PUSH_VAPID_CONTACT", "mailto:support@civiccode.app")


def can_send_push() -> bool:
    return bool(VAPID_PUBLIC_KEY and VAPID_PRIVATE_KEY)


def _payload_from_notification(notification: NotificationResponse) -> Dict[str, Any]:
    created_at = notification.created_at.isoformat() if isinstance(notification.created_at, datetime) else None
    return {
        "title": notification.title or "CodeSoft",
        "body": notification.body or notification.origin_label or "Open CodeSoft for more details.",
        "data": {
            "url": notification.origin_url_path or "/notifications",
            "notificationId": notification.id,
            "originLabel": notification.origin_label,
            "createdAt": created_at,
        },
    }


def _send_payload_to_subscriptions(subscriptions: Iterable[PushSubscription], payload: Dict[str, Any]) -> Iterable[int]:
    invalid_ids = []
    serialized = json.dumps(payload)
    for subscription in subscriptions:
        try:
            webpush(
                subscription_info={
                    "endpoint": subscription.endpoint,
                    "keys": {"p256dh": subscription.p256dh, "auth": subscription.auth},
                },
                data=serialized,
                vapid_private_key=VAPID_PRIVATE_KEY,
                vapid_claims={"sub": VAPID_CONTACT},
            )
        except WebPushException as exc:
            status_code = getattr(getattr(exc, "response", None), "status_code", None)
            if status_code in (404, 410):
                invalid_ids.append(subscription.id)
            else:
                logger.warning("Web push failed for subscription %s: %s", subscription.id, exc)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Unexpected web push failure for subscription %s: %s", subscription.id, exc)
    return invalid_ids


def send_push_payload(db: Session, user_id: int, payload: Dict[str, Any]) -> bool:
    if not can_send_push():
        return False

    subscriptions = (
        db.query(PushSubscription)
        .filter(PushSubscription.user_id == user_id)
        .all()
    )
    if not subscriptions:
        return False

    invalid_ids = _send_payload_to_subscriptions(subscriptions, payload)
    if invalid_ids:
        db.query(PushSubscription).filter(PushSubscription.id.in_(invalid_ids)).delete(synchronize_session=False)
        db.commit()
    return True


def send_push_for_notification(db: Session, notification: NotificationResponse) -> bool:
    payload = _payload_from_notification(notification)
    return send_push_payload(db, notification.user_id, payload)
