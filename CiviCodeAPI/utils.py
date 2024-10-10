# utils.py or in your users.py file
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password, encrypted_password):
    return pwd_context.verify(plain_password, encrypted_password)

def hash_password(password):
    return pwd_context.hash(password)