from passlib.context import CryptContext
from datetime import datetime, timedelta
from pytz import timezone
from dateutil.relativedelta import relativedelta

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password, encrypted_password):
    """
    Verify a password against its hash.

    Args:
        plain_password (str): The plain text password.
        encrypted_password (str): The hashed password.

    Returns:
        bool: True if the password matches, False otherwise.
    """
    return pwd_context.verify(plain_password, encrypted_password)

def hash_password(password):
    """
    Hash a password.

    Args:
        password (str): The password to hash.

    Returns:
        str: The hashed password.
    """
    return pwd_context.hash(password)

def _normalize_start_day(start_day: str) -> int:
    """
    Map start_day string to Python weekday index (Mon=0..Sun=6).

    Args:
        start_day (str): The name or abbreviation of the day.

    Returns:
        int: The Python weekday index (0 for Monday, 6 for Sunday).
    """
    key = (start_day or 'mon').strip().lower()
    mapping = {
        'mon': 0,
        'monday': 0,
        'sun': 6,
        'sunday': 6,
        'sat': 5,
        'saturday': 5,
        'tue': 1, 'tuesday': 1,
        'wed': 2, 'wednesday': 2,
        'thu': 3, 'thursday': 3,
        'fri': 4, 'friday': 4,
    }
    return mapping.get(key, 0)

def get_last_workweek(start_day: str = 'mon'):
    """
    Calculate the start and end datetimes for the previous workweek.

    Args:
        start_day (str): The starting day of the week (default is 'mon').

    Returns:
        tuple[datetime, datetime]: A tuple containing the start and end datetimes of the last workweek.
    """
    tz_now = datetime.now(timezone('US/Eastern'))
    desired = _normalize_start_day(start_day)
    # Days since start of this week, then add 7 more for last week
    days_since_start = (tz_now.weekday() - desired) % 7
    start_of_last_week = (tz_now - timedelta(days=days_since_start + 7)).replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_last_week = (start_of_last_week + timedelta(days=6)).replace(hour=23, minute=59, second=59, microsecond=999999)
    return start_of_last_week, end_of_last_week

def get_this_workweek(start_day: str = 'mon'):
    """
    Calculate the start and end datetimes for the current workweek.

    Args:
        start_day (str): The starting day of the week (default is 'mon').

    Returns:
        tuple[datetime, datetime]: A tuple containing the start and end datetimes of the current workweek.
    """
    tz_now = datetime.now(timezone('US/Eastern'))
    desired = _normalize_start_day(start_day)
    days_since_start = (tz_now.weekday() - desired) % 7
    start_of_this_week = (tz_now - timedelta(days=days_since_start)).replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_this_week = (start_of_this_week + timedelta(days=6)).replace(hour=23, minute=59, second=59, microsecond=999999)
    return start_of_this_week, end_of_this_week