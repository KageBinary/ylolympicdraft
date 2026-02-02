from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import text

from db.session import get_db
from core.security import (
    get_password_hash,
    verify_password,
    create_access_token,
)
from api.deps import get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])


# ---------- Schemas ----------

class RegisterIn(BaseModel):
    username: str = Field(min_length=3, max_length=32)
    password: str = Field(min_length=6, max_length=128)


class LoginIn(BaseModel):
    username: str
    password: str


# ---------- Helpers ----------

def _get_user_by_username(db: Session, username: str):
    return db.execute(
        text(
            """
            select id, username, password_hash, created_at
            from public.users
            where username = :u
            """
        ),
        {"u": username},
    ).mappings().first()


# ---------- Routes ----------

@router.post("/register")
def register(
    body: RegisterIn,
    db: Session = Depends(get_db),
):
    existing = _get_user_by_username(db, body.username)
    if existing:
        raise HTTPException(status_code=409, detail="Username already taken")

    password_hash = get_password_hash(body.password)

    try:
        user = db.execute(
            text(
                """
                insert into public.users (username, password_hash)
                values (:u, :ph)
                returning id, username, created_at
                """
            ),
            {"u": body.username, "ph": password_hash},
        ).mappings().first()

        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to create user")

    token = create_access_token({"sub": str(user["id"])})

    return {
        "user": dict(user),
        "access_token": token,
        "token_type": "bearer",
    }


@router.post("/login")
def login(
    body: LoginIn,
    db: Session = Depends(get_db),
):
    user = _get_user_by_username(db, body.username)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    if not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid username or password")

    token = create_access_token({"sub": str(user["id"])})

    return {
        "user": {
            "id": str(user["id"]),
            "username": user["username"],
            "created_at": user["created_at"],
        },
        "access_token": token,
        "token_type": "bearer",
    }


@router.get("/me")
def auth_me(user=Depends(get_current_user)):
    return user
