from passlib.context import CryptContext
from datetime import datetime, timedelta
from pytz import timezone
from dateutil.relativedelta import relativedelta

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password, encrypted_password):
    return pwd_context.verify(plain_password, encrypted_password)

def hash_password(password):
    return pwd_context.hash(password)

def get_last_workweek():
    today = datetime.now(timezone('US/Eastern'))
    start_of_last_week = (today - timedelta(days=today.weekday() + 7)).replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_last_week = (start_of_last_week + timedelta(days=6)).replace(hour=23, minute=59, second=59, microsecond=999999)
    return start_of_last_week, end_of_last_week

def get_this_workweek():
    today = datetime.now(timezone('US/Eastern'))
    start_of_this_week = today - timedelta(days=today.weekday())
    end_of_this_week = start_of_this_week + timedelta(days=6)
    return start_of_this_week.replace(hour=0, minute=0, second=0, microsecond=0), end_of_this_week.replace(hour=23, minute=59, second=59, microsecond=999999)