from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
import jwt

from CiviCodeAPI.database import get_db
from CiviCodeAPI.models import User

SECRET_KEY = "trpdds2020"
ALGORITHM = "HS256"
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login")


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = int(payload.get("sub"))
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


from typing import Optional
from fastapi import Request


async def get_current_user_optional(request: Request, db: Session = Depends(get_db)) -> Optional[User]:
    """Optional current user dependency.

    Reads Authorization: Bearer <token> from headers. If a valid token is present
    returns the corresponding User. If no token or an invalid token is present,
    returns None (does not raise a 401).
    """
    auth: Optional[str] = request.headers.get("authorization")
    if not auth:
        return None
    parts = auth.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    token = parts[1]
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = int(payload.get("sub"))
    except Exception:
        return None
    user = db.query(User).filter(User.id == user_id).first()
    return user
