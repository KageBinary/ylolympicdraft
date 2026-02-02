# backend/core/security.py
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import jwt
from passlib.context import CryptContext
from jwt import PyJWTError


pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

JWT_SECRET = os.getenv("JWT_SECRET", "")
JWT_ALG = os.getenv("JWT_ALG", "HS256")

if not JWT_SECRET:
    raise RuntimeError("JWT_SECRET missing in backend/.env")


# -------------------------
# Password helpers
# -------------------------

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    return pwd_context.verify(plain_password, password_hash)


# -------------------------
# JWT helpers
# -------------------------

def create_access_token(
    data: Dict[str, Any],
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    Create a signed JWT access token.
    Expects `data` to include at least {"sub": user_id}.
    """
    to_encode = dict(data)

    now = datetime.now(timezone.utc)
    expire = now + (expires_delta or timedelta(days=7))

    to_encode.update(
        {
            "iat": int(now.timestamp()),
            "exp": int(expire.timestamp()),
        }
    )

    return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALG)


def decode_token(token: str) -> Dict[str, Any]:
    """
    Decode and validate a JWT.
    Raises jwt.PyJWTError if invalid or expired.
    """
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
        return payload
    except PyJWTError:
        # Let the caller decide how to turn this into HTTP 401
        raise
