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
        {"lid": league_id, "uid": user_id},
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
    draft_rounds: int = Field(default=20, ge=1, le=116)


class JoinLeagueIn(BaseModel):
    code: str = Field(min_length=3, max_length=32)


@router.post("/create")
def create_league(
    body: CreateLeagueIn,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    league_row = None

    for _ in range(5):
        code = _make_league_code()
        try:
            # 1) create league (NO commit yet)
            league_row = db.execute(
                text(
                    """
                    insert into public.leagues (code, name, status, commissioner_id, draft_rounds)
                    values (:code, :name, 'lobby', :cid, :dr)
                    returning id, code, name, status, commissioner_id, draft_rounds, created_at
                    """
                ),
                {"code": code, "name": body.name, "cid": user["id"], "dr": body.draft_rounds},
            ).mappings().first()

            # 2) auto-join commissioner (still NO commit yet)
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

            # 3) commit ONCE (atomic)
            db.commit()
            break

        except Exception:
            db.rollback()
            league_row = None

    if not league_row:
        raise HTTPException(status_code=500, detail="Failed to create league")

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
    - generates league_events ONCE using leagues.draft_rounds
      - auto events: (total events - draft_rounds) chosen randomly
      - draft events: the remaining events
      - sort_order preserved from events.sort_order
    - randomizes draft order ONCE by assigning league_members.draft_position = 1..N
    - sets league.status = 'drafting'
    """
    _require_commissioner(db, league_id, user["id"])

    league = db.execute(
        text("select status, draft_rounds from public.leagues where id=:lid"),
        {"lid": league_id},
    ).mappings().first()

    if not league:
        raise HTTPException(status_code=404, detail="League not found")

    if league["status"] != "lobby":
        raise HTTPException(status_code=409, detail=f"League not in lobby (status: {league['status']})")

    # Ensure events are seeded
    events_count_row = db.execute(text("select count(*) as c from public.events")).mappings().first()
    events_count = int(events_count_row["c"]) if events_count_row else 0
    if events_count <= 0:
        raise HTTPException(status_code=400, detail="No events seeded")

    draft_rounds = int(league["draft_rounds"])
    if draft_rounds < 1 or draft_rounds > events_count:
        raise HTTPException(status_code=400, detail="Invalid draft_rounds for current events")

    # Prevent double-generation (events should be generated exactly once)
    already = db.execute(
        text("select 1 from public.league_events where league_id=:lid limit 1"),
        {"lid": league_id},
    ).first()
    if already:
        raise HTTPException(status_code=409, detail="League events already generated")

    auto_count = events_count - draft_rounds

    # Generate league_events: randomly pick auto events, remaining are draft events
    db.execute(
        text(
            """
            with auto_events as (
              select id
              from public.events
              order by random()
              limit :auto_n
            )
            insert into public.league_events (league_id, event_id, mode, sort_order)
            select
              :lid,
              e.id,
              case when a.id is not null then 'auto' else 'draft' end as mode,
              e.sort_order
            from public.events e
            left join auto_events a on a.id = e.id
            """
        ),
        {"lid": league_id, "auto_n": auto_count},
    )

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

    # Single commit for: league_events + draft positions + status update
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

    return {
        "ok": True,
        "league_id": league_id,
        "status": "drafting",
        "draft_order": [dict(r) for r in order],
        "draft_rounds": draft_rounds,
        "auto_rounds": auto_count,
    }


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
            select l.id, l.code, l.name, l.status, l.commissioner_id, l.created_at, l.draft_rounds
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
            """
            select id, code, name, status, commissioner_id, draft_rounds, created_at
            from public.leagues
            where id = :lid
            """
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
