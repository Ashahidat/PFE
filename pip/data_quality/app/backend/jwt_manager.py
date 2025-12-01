from datetime import datetime, timedelta
from jose import jwt

SECRET_KEY = "23HnfK4lP9zQeW8yXv7aBcDeFgHiJkLmNoPqRsTuVwXyZ0123456789AbCdEfGhIj" # clé random que j'ai écrite moi-même
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60  # en minutes 

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    token = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return token

def verify_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload   # le contenu du token : {"sub": employee_id, "username":} c'est ce que moi je vais y mettre
    except Exception:
        return None


