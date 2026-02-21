from datetime import datetime, timedelta
from jose import jwt

SECRET_KEY = "23HnfK4lP9zQeW8yXv7aBcD"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 180

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    token = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return token

def verify_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except Exception:
        return None