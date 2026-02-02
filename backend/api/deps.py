# backend/api/deps.py
from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from sqlalchemy import text
import jwt  # PyJWT exceptions

from db.session import get_db
from core.security import decode_token

# This is what makes Swagger render the 🔒 Authorize button
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def _get_token_from_request(request: Request) -> str | None:
    """
    Support either:
      - Cookie: access_token=<jwt>
      - Header: Authorization: Bearer <jwt>
    """
    token = request.cookies.get("access_token")
    if token:
        return token

    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        return auth.split(" ", 1)[1].strip()

    return None


def get_current_user(
    # Swagger prefers this; sends Authorization header when you click Authorize
    token: str = Depends(oauth2_scheme),
    # Also allows cookie token to work (useful for browser sessions)
    request: Request = None,  # FastAPI will inject it
    db: Session = Depends(get_db),
):
    # If oauth2_scheme didn’t find a header token, fall back to cookie/header manually
    if not token:
        token = _get_token_from_request(request) if request else None

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    try:
        payload = decode_token(token)
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
        )

    user = db.execute(
        text("select id, username from public.users where id=:uid"),
        {"uid": user_id},
    ).mappings().first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    return dict(user)
