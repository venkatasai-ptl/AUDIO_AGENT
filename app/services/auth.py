# app/services/auth.py
import datetime as dt
import os
from jose import jwt, JWTError
from passlib.context import CryptContext

PWDCTX = CryptContext(schemes=["bcrypt"], deprecated="auto")
ALGO = "HS256"

JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-change-me")
ACCESS_TOKEN_MIN = int(os.getenv("ACCESS_TOKEN_MINUTES", "45"))

def hash_password(pw: str) -> str:
    return PWDCTX.hash(pw)

def verify_password(pw: str, pw_hash: str) -> bool:
    return PWDCTX.verify(pw, pw_hash)

def create_access_token(sub: str) -> str:
    now = dt.datetime.utcnow()
    payload = {
        "sub": sub,
        "iat": int(now.timestamp()),
        "exp": int((now + dt.timedelta(minutes=ACCESS_TOKEN_MIN)).timestamp()),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=ALGO)

def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[ALGO])
    except JWTError:
        return None
