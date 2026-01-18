# auth.py
import os
import time
import jwt
from typing import Literal, Optional
from fastapi import HTTPException, status, Depends, Cookie
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from stadiums_config import STADIUMS, ADMIN_PASSWORD

JWT_SECRET = os.getenv("FOV_JWT_SECRET", "dev-secret-change-me")
JWT_ALG = "HS256"
BEARER = HTTPBearer(auto_error=False)

SubjectType = Literal["admin", "stadium"]

def verify_stadium_password(stadium_slug: str, password: str) -> bool:
    if stadium_slug not in STADIUMS:
        return False
    return STADIUMS[stadium_slug].get("password") == password

def verify_admin_password(username: str, password: str) -> bool:
    if username.lower() != "admin":
        return False
    return password == ADMIN_PASSWORD

def create_access_token(sub_type: SubjectType, sub_value: str, expires_seconds: int = 60*60*12) -> str:
    now = int(time.time())
    payload = {
        "iat": now,
        "exp": now + expires_seconds,
        "sub_type": sub_type,  # "admin" or "stadium"
        "sub": sub_value,      # stadium slug or "admin"
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)

def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

def get_current_subject(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(BEARER),
    access_token: Optional[str] = Cookie(default=None)  # optional cookie fallback
) -> dict:
    token = None
    if creds and creds.scheme.lower() == "bearer":
        token = creds.credentials
    elif access_token:
        token = access_token
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return decode_token(token)

def is_admin(claims: dict) -> bool:
    return claims.get("sub_type") == "admin"

def stadium_from_claims(claims: dict) -> Optional[str]:
    return claims.get("sub") if claims.get("sub_type") == "stadium" else None
