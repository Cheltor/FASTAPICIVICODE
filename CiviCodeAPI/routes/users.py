from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from typing import List, Union
from models import User
from schemas import UserResponse, UserCreate, UserUpdate, PasswordResetRequest, PasswordResetConfirm
from database import get_db
from utils import verify_password, hash_password
from datetime import datetime, timedelta
import jwt
import secrets
from email_service import send_password_reset_email, FRONTEND_BASE_URL

SECRET_KEY = "trpdds2020"  
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 480
PASSWORD_RESET_EXPIRE_MINUTES = 60

def create_access_token(data: dict, expires_delta: Union[timedelta, None] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

router = APIRouter()


@router.get("/users/search", response_model=List[UserResponse])
def search_users(q: str = "", db: Session = Depends(get_db)):
    """
    Simple user search by name or email (used for @-mentions).

    Args:
        q (str): Search query.
        db (Session): The database session.

    Returns:
        list[UserResponse]: A list of matching users.
    """
    if not q:
        return []
    q_like = f"%{q}%"
    users = db.query(User).filter((User.name.ilike(q_like)) | (User.email.ilike(q_like))).limit(20).all()
    return users

# Show all the users
@router.get("/users/", response_model=List[UserResponse])
def get_users(skip: int = 0, db: Session = Depends(get_db)):
    """
    Get all users.

    Args:
        skip (int): Pagination offset.
        db (Session): The database session.

    Returns:
        list[UserResponse]: A list of users.
    """
    users = db.query(User).order_by(User.created_at.desc()).offset(skip).all()
    return users

# Get users by ONS
@router.get("/users/ons/", response_model=List[UserResponse])
def get_ons_users(db: Session = Depends(get_db)):
    """
    Get users with ONS role (role == 1).

    Args:
        db (Session): The database session.

    Returns:
        list[UserResponse]: A list of ONS users.
    """
    users = db.query(User).filter(User.role == 1).all()
    return users

# login
@router.post("/login")
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """
    Authenticate user and return access token.

    Args:
        form_data (OAuth2PasswordRequestForm): Login credentials.
        db (Session): The database session.

    Returns:
        dict: Access token and type.

    Raises:
        HTTPException: If authentication fails.
    """
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.encrypted_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Create a token with the user ID as payload
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    token = create_access_token(
        data={"sub": str(user.id)}, expires_delta=access_token_expires
    )

    return {"access_token": token, "token_type": "bearer"}

# Get the current user
@router.get("/user", response_model=UserResponse)
async def read_users_me(
    token: str = Depends(OAuth2PasswordBearer(tokenUrl="/login")),
    db: Session = Depends(get_db)
):
    """
    Get the current authenticated user.

    Args:
        token (str): OAuth2 token.
        db (Session): The database session.

    Returns:
        UserResponse: The current user.

    Raises:
        HTTPException: If user not found or token invalid.
    """
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    user_id = int(payload.get("sub"))
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user

# Get a specific user by ID
@router.get("/users/{user_id}", response_model=UserResponse)
def get_user(user_id: int, db: Session = Depends(get_db)):
    """
    Get a user by ID.

    Args:
        user_id (int): The ID of the user.
        db (Session): The database session.

    Returns:
        UserResponse: The user details.

    Raises:
        HTTPException: If user not found.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

# Create a new user
@router.post("/users/", response_model=UserResponse)
def create_user(user: UserCreate, db: Session = Depends(get_db)):
    """
    Create a new user.

    Args:
        user (UserCreate): User data.
        db (Session): The database session.

    Returns:
        UserResponse: The created user.
    """
    new_user = User(**user.dict())
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

# Update a user
@router.put("/users/{user_id}", response_model=UserResponse)
def update_user(user_id: int, user: UserUpdate, db: Session = Depends(get_db)):
    """
    Update a user.

    Args:
        user_id (int): The ID of the user.
        user (UserUpdate): Updated user data.
        db (Session): The database session.

    Returns:
        UserResponse: The updated user.

    Raises:
        HTTPException: If user not found.
    """
    db_user = db.query(User).filter(User.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Update the user
    for key, value in user.dict(exclude_unset=True).items():
        setattr(db_user, key, value)
    
    db.commit()
    db.refresh(db_user)
    return db_user

# Delete a user
@router.delete("/users/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db)):
    """
    Delete a user.

    Args:
        user_id (int): The ID of the user.
        db (Session): The database session.

    Returns:
        dict: Confirmation message.

    Raises:
        HTTPException: If user not found.
    """
    db_user = db.query(User).filter(User.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    db.delete(db_user)
    db.commit()
    return {"message": "User deleted successfully"}

@router.post("/password/forgot")
async def forgot_password(
    payload: PasswordResetRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Initiate password reset process.

    Args:
        payload (PasswordResetRequest): Request containing email.
        background_tasks (BackgroundTasks): Background tasks handler.
        db (Session): The database session.

    Returns:
        dict: Status message.
    """
    user = db.query(User).filter(User.email == payload.email).first()
    if user:
        token = secrets.token_urlsafe(32)
        user.reset_password_token = token
        user.reset_password_sent_at = datetime.utcnow()
        db.add(user)
        db.commit()

        reset_url = None
        if FRONTEND_BASE_URL:
            reset_url = f"{FRONTEND_BASE_URL.rstrip('/')}/reset-password?token={token}"
        background_tasks.add_task(send_password_reset_email, user.email, reset_url)

    # Always return success response to avoid leaking account existence
    return {"message": "If an account exists for that email, a reset link has been sent."}

@router.post("/password/reset")
async def reset_password(
    payload: PasswordResetConfirm,
    db: Session = Depends(get_db)
):
    """
    Complete password reset process.

    Args:
        payload (PasswordResetConfirm): Token and new password.
        db (Session): The database session.

    Returns:
        dict: Success message.

    Raises:
        HTTPException: If token invalid/expired or password too short.
    """
    user = db.query(User).filter(User.reset_password_token == payload.token).first()
    if not user or not user.reset_password_sent_at:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired reset token")

    expiration_time = user.reset_password_sent_at + timedelta(minutes=PASSWORD_RESET_EXPIRE_MINUTES)
    if datetime.utcnow() > expiration_time:
        # Clear out expired token to avoid reuse
        user.reset_password_token = None
        user.reset_password_sent_at = None
        db.add(user)
        db.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired reset token")

    if len(payload.password) < 8:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password must be at least 8 characters long")

    user.encrypted_password = hash_password(payload.password)
    user.reset_password_token = None
    user.reset_password_sent_at = None
    db.add(user)
    db.commit()

    return {"message": "Password updated successfully."}
