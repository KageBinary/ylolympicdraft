from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import text

from db.session import get_db
from core.security import (
    get_password_hash,
    verify_password,
    create_access_token,
)

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


def _user_public(user_row):
    return {
        "id": str(user_row["id"]),
        "username": user_row["username"],
        "created_at": user_row["created_at"],
    }


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
    except Exception as e:
        db.rollback()
        # If the DB unique constraint on users.username trips, return 409 (not 500).
        msg = str(e).lower()
        if "unique" in msg and "username" in msg:
            raise HTTPException(status_code=409, detail="Username already taken")
        raise HTTPException(status_code=500, detail="Failed to create user")

    token = create_access_token({"sub": str(user["id"])})

    return {
        "user": dict(user),
        "access_token": token,
        "token_type": "bearer",
    }


@router.post("/login")
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """
    OAuth2 Password Flow login (Swagger uses this).
    Sends credentials as form data: username=...&password=...
    """
    user = _get_user_by_username(db, form_data.username)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    if not verify_password(form_data.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid username or password")

    token = create_access_token({"sub": str(user["id"])})

    return {
        "user": _user_public(user),
        "access_token": token,
        "token_type": "bearer",
    }


@router.post("/login-json")
def login_json(
    body: LoginIn,
    db: Session = Depends(get_db),
):
    """
    Optional JSON login endpoint (handy for frontends that post JSON).
    """
    user = _get_user_by_username(db, body.username)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    if not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid username or password")

    token = create_access_token({"sub": str(user["id"])})

    return {
        "user": _user_public(user),
        "access_token": token,
        "token_type": "bearer",
    }
