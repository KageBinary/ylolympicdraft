from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import text

from db.session import get_db
from api.deps import get_current_user

router = APIRouter(prefix="/draft", tags=["draft"])


class MakePickIn(BaseModel):
    league_id: str
    entry_key: str = Field(min_length=1, max_length=200)
    entry_name: str = Field(min_length=1, max_length=200)


def _require_member(db: Session, league_id: str, user_id: str) -> None:
    row = db.execute(
        text("select 1 from public.league_members where league_id=:lid and user_id=:uid"),
        {"lid": league_id, "uid": user_id},
    ).first()
    if not row:
        raise HTTPException(status_code=403, detail="Not a member of this league")


def _require_drafting(db: Session, league_id: str) -> None:
    row = db.execute(
        text("select status from public.leagues where id=:lid"),
        {"lid": league_id},
    ).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="League not found")
    if row["status"] != "drafting":
        raise HTTPException(status_code=409, detail=f"Draft not active (status: {row['status']})")


def _get_members_in_draft_order(db: Session, league_id: str):
    members = db.execute(
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

    if not members:
        raise HTTPException(status_code=400, detail="League has no members")

    if members[0]["draft_position"] is None:
        raise HTTPException(status_code=409, detail="Draft order not set. Commissioner must start the draft.")

    return members


def _get_events_in_order(db: Session):
    return db.execute(
        text(
            """
            select id, sport, name, event_key, is_team_event, sort_order
            from public.events
            order by sort_order asc
            """
        )
    ).mappings().all()


def _get_picks_for_event(db: Session, league_id: str, event_id: str):
    # IMPORTANT: do NOT select p.id (some schemas won't have it)
    return db.execute(
        text(
            """
            select p.user_id, u.username, p.entry_key, p.entry_name, p.picked_at
            from public.draft_picks p
            join public.users u on u.id = p.user_id
            where p.league_id = :lid and p.event_id = :eid
            order by p.picked_at asc
            """
        ),
        {"lid": league_id, "eid": event_id},
    ).mappings().all()


def _current_state(db: Session, league_id: str):
    members = _get_members_in_draft_order(db, league_id)

    events = _get_events_in_order(db)
    if not events:
        raise HTTPException(status_code=400, detail="No events seeded")

    n = len(members)

    for idx, ev in enumerate(events):
        picks = _get_picks_for_event(db, league_id, str(ev["id"]))
        if len(picks) < n:
            forward = (idx % 2 == 0)
            order = members if forward else list(reversed(members))
            on_the_clock = order[len(picks)]

            return {
                "complete": False,
                "event": dict(ev),
                "event_index": idx,
                "direction": "forward" if forward else "reverse",
                "members": [dict(m) for m in members],
                "picks": [dict(p) for p in picks],
                "on_the_clock": {"id": str(on_the_clock["id"]), "username": on_the_clock["username"]},
            }

    return {
        "complete": True,
        "event": None,
        "event_index": None,
        "direction": None,
        "members": [dict(m) for m in members],
        "picks": [],
        "on_the_clock": None,
    }


@router.get("/state")
def draft_state(
    league_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    _require_member(db, league_id, user["id"])
    return _current_state(db, league_id)


@router.post("/pick")
def make_pick(
    body: MakePickIn,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    league_id = body.league_id

    _require_member(db, league_id, user["id"])
    _require_drafting(db, league_id)

    state = _current_state(db, league_id)
    if state["complete"]:
        raise HTTPException(status_code=409, detail="Draft is complete")

    if state["on_the_clock"]["id"] != str(user["id"]):
        raise HTTPException(status_code=409, detail="Not your turn")

    event_id = str(state["event"]["id"])

    try:
        # IMPORTANT: don't RETURN id (some schemas won't have it)
        row = db.execute(
            text(
                """
                insert into public.draft_picks (league_id, event_id, user_id, entry_key, entry_name)
                values (:lid, :eid, :uid, :ek, :en)
                returning league_id, event_id, user_id, entry_key, entry_name, picked_at
                """
            ),
            {
                "lid": league_id,
                "eid": event_id,
                "uid": str(user["id"]),
                "ek": body.entry_key.strip(),
                "en": body.entry_name.strip(),
            },
        ).mappings().first()

        db.commit()

    except Exception as e:
        db.rollback()
        # Show the real DB error so your smoke test can tell you exactly what constraint/schema failed.
        raise HTTPException(status_code=409, detail=f"Pick rejected: {str(e)}")

    return {"ok": True, "pick": dict(row), "state": _current_state(db, league_id)}
