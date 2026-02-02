import secrets
import string
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import text

from db.session import get_db
from api.deps import get_current_user

router = APIRouter(prefix="/leagues", tags=["leagues"])


def _make_league_code() -> str:
    # Friendly invite codes like: YL-AB12CD
    alphabet = string.ascii_uppercase + string.digits
    return "YL-" + "".join(secrets.choice(alphabet) for _ in range(6))


def _require_commissioner(db: Session, league_id: str, user_id: str) -> None:
    row = db.execute(
        text("select commissioner_id from public.leagues where id=:lid"),
        {"lid": league_id},
    ).mappings().first()

    if not row:
        raise HTTPException(status_code=404, detail="League not found")

    if str(row["commissioner_id"]) != str(user_id):
        raise HTTPException(status_code=403, detail="Commissioner only")


def _require_member(db: Session, league_id: str, user_id: str) -> None:
    row = db.execute(
        text("select 1 from public.league_members where league_id=:lid and user_id=:uid"),
        {"lid": league_id, "uid": user_id},
    ).first()
    if not row:
        raise HTTPException(status_code=403, detail="Not a member of this league")


class CreateLeagueIn(BaseModel):
    name: str = Field(default="YL Olympic Draft", min_length=3, max_length=60)


class JoinLeagueIn(BaseModel):
    code: str = Field(min_length=3, max_length=32)


@router.post("/create")
def create_league(
    body: CreateLeagueIn,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    # Ensure unique code (retry a few times)
    league_row = None
    for _ in range(5):
        code = _make_league_code()
        try:
            league_row = db.execute(
                text(
                    """
                    insert into public.leagues (code, name, status, commissioner_id)
                    values (:code, :name, 'lobby', :cid)
                    returning id, code, name, status, commissioner_id, created_at
                    """
                ),
                {"code": code, "name": body.name, "cid": user["id"]},
            ).mappings().first()
            db.commit()
            break
        except Exception:
            db.rollback()
            league_row = None

    if not league_row:
        raise HTTPException(status_code=500, detail="Failed to create league code")

    # Auto-join commissioner
    db.execute(
        text(
            """
            insert into public.league_members (league_id, user_id)
            values (:lid, :uid)
            on conflict do nothing
            """
        ),
        {"lid": league_row["id"], "uid": user["id"]},
    )
    db.commit()

    return dict(league_row)


@router.post("/join")
def join_league(
    body: JoinLeagueIn,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    league = db.execute(
        text("select id, code, name, status, commissioner_id from public.leagues where code = :c"),
        {"c": body.code.upper()},
    ).mappings().first()

    if not league:
        raise HTTPException(status_code=404, detail="League not found")

    # Prevent late-joins once the draft starts (keeps order stable)
    if league["status"] != "lobby":
        raise HTTPException(status_code=409, detail="League already started; cannot join now")

    db.execute(
        text(
            """
            insert into public.league_members (league_id, user_id)
            values (:lid, :uid)
            on conflict do nothing
            """
        ),
        {"lid": league["id"], "uid": user["id"]},
    )
    db.commit()

    return {"ok": True, "league": dict(league)}


@router.post("/{league_id}/start")
def start_draft(
    league_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """
    Commissioner starts the draft:
    - randomizes draft order ONCE by assigning league_members.draft_position = 1..N
    - sets league.status = 'drafting'
    """
    _require_commissioner(db, league_id, user["id"])

    league = db.execute(
        text("select status from public.leagues where id=:lid"),
        {"lid": league_id},
    ).mappings().first()

    if not league:
        raise HTTPException(status_code=404, detail="League not found")

    if league["status"] != "lobby":
        raise HTTPException(status_code=409, detail=f"League not in lobby (status: {league['status']})")

    # Assign random draft positions to current members (1..N)
    # Assign random draft positions to current members (1..N)
    db.execute(
        text(
            """
            with shuffled as (
              select
                user_id,
                row_number() over (order by random()) as pos
              from public.league_members
              where league_id = :lid
            )
            update public.league_members m
            set draft_position = s.pos
            from shuffled s
            where m.league_id = :lid
              and m.user_id = s.user_id
            """
        ),
        {"lid": league_id},
    )


    # Start drafting
    db.execute(
        text("update public.leagues set status='drafting' where id=:lid"),
        {"lid": league_id},
    )

    db.commit()

    order = db.execute(
        text(
            """
            select u.id, u.username, m.draft_position
            from public.league_members m
            join public.users u on u.id = m.user_id
            where m.league_id = :lid
            order by m.draft_position asc, u.id asc
            """
        ),
        {"lid": league_id},
    ).mappings().all()

    return {"ok": True, "league_id": league_id, "status": "drafting", "draft_order": [dict(r) for r in order]}


@router.post("/{league_id}/lock")
def lock_league(
    league_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """
    Commissioner locks the league:
    - sets league.status = 'locked'
    After this, results can be submitted (per results.py).
    """
    _require_commissioner(db, league_id, user["id"])

    league = db.execute(
        text("select status from public.leagues where id=:lid"),
        {"lid": league_id},
    ).mappings().first()
    if not league:
        raise HTTPException(status_code=404, detail="League not found")

    if league["status"] == "lobby":
        raise HTTPException(status_code=409, detail="Cannot lock before draft starts")

    db.execute(
        text("update public.leagues set status='locked' where id=:lid"),
        {"lid": league_id},
    )
    db.commit()

    return {"ok": True, "league_id": league_id, "status": "locked"}


@router.get("/{league_id}/draft-order")
def draft_order(
    league_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    _require_member(db, league_id, user["id"])

    rows = db.execute(
        text(
            """
            select u.id, u.username, m.draft_position
            from public.league_members m
            join public.users u on u.id = m.user_id
            where m.league_id = :lid
            order by m.draft_position asc nulls last, u.id asc
            """
        ),
        {"lid": league_id},
    ).mappings().all()

    return {"league_id": league_id, "draft_order": [dict(r) for r in rows]}


@router.get("/mine")
def my_leagues(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    rows = db.execute(
        text(
            """
            select l.id, l.code, l.name, l.status, l.commissioner_id, l.created_at
            from public.leagues l
            join public.league_members m on m.league_id = l.id
            where m.user_id = :uid
            order by l.created_at desc
            """
        ),
        {"uid": user["id"]},
    ).mappings().all()

    return [dict(r) for r in rows]


@router.get("/{league_id}")
def league_detail(
    league_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    _require_member(db, league_id, user["id"])

    league = db.execute(
        text(
            "select id, code, name, status, commissioner_id, created_at from public.leagues where id = :lid"
        ),
        {"lid": league_id},
    ).mappings().first()

    members = db.execute(
        text(
            """
            select u.id, u.username, m.joined_at, m.draft_position
            from public.league_members m
            join public.users u on u.id = m.user_id
            where m.league_id = :lid
            order by
              m.draft_position asc nulls last,
              m.joined_at asc,
              u.id asc
            """
        ),
        {"lid": league_id},
    ).mappings().all()

    return {
        "league": dict(league) if league else None,
        "members": [dict(m) for m in members],
    }
