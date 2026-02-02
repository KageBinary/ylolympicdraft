from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy import text

from db.session import get_db
from core.security import decode_token

def _get_token(request: Request) -> str | None:
    # Prefer cookie
    token = request.cookies.get("access_token")
    if token:
        return token

    # Fallback: Bearer token
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        return auth.split(" ", 1)[1].strip()

    return None

def get_current_user(request: Request, db: Session = Depends(get_db)):
    token = _get_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        payload = decode_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")

    row = db.execute(
        text("select id, username, created_at from public.users where id = :id"),
        {"id": user_id},
    ).mappings().first()

    if not row:
        raise HTTPException(status_code=401, detail="User not found")

    return dict(row)
