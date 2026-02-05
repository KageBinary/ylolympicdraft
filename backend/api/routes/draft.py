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


def _get_events_in_order(db: Session, league_id: str, member_count: int):
    total_draft_events_row = db.execute(
        text(
            """
            select count(*) as c
            from public.league_events
            where league_id = :lid and mode = 'draft'
            """
        ),
        {"lid": league_id},
    ).mappings().first()
    total_draft_events = int(total_draft_events_row["c"]) if total_draft_events_row else 0
    if total_draft_events <= 0:
        # Either events not seeded or league_events not generated yet.
        # start_draft generates league_events, so this message is the most helpful.
        raise HTTPException(status_code=409, detail="Draft events not set. Commissioner must start the draft.")

    # Ignore draft events that currently cannot support one unique pick per member.
    return db.execute(
        text(
            """
            with entry_counts as (
              select event_id, count(*) as c
              from public.event_entries
              group by event_id
            )
            select e.id, e.sport, e.name, e.event_key, e.is_team_event, le.sort_order
            from public.league_events le
            join public.events e on e.id = le.event_id
            left join entry_counts ec on ec.event_id = e.id
            where le.league_id = :lid
              and le.mode = 'draft'
              and coalesce(ec.c, 0) >= :member_count
            order by le.sort_order asc
            """
        ),
        {"lid": league_id, "member_count": member_count},
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

    n = len(members)
    events = _get_events_in_order(db, league_id, n)

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

    entry_key = body.entry_key.strip()
    entry_name = body.entry_name.strip()

    if not entry_key:
        raise HTTPException(status_code=400, detail="entry_key cannot be blank")
    if not entry_name:
        raise HTTPException(status_code=400, detail="entry_name cannot be blank")

    _require_member(db, league_id, user["id"])
    _require_drafting(db, league_id)

    state = _current_state(db, league_id)
    if state["complete"]:
        raise HTTPException(status_code=409, detail="Draft is complete")

    if state["on_the_clock"]["id"] != str(user["id"]):
        raise HTTPException(status_code=409, detail="Not your turn")

    event_id = str(state["event"]["id"])
    entry_row = db.execute(
        text(
            """
            select entry_key, entry_name
            from public.event_entries
            where event_id = :eid
              and entry_key = :ek
            """
        ),
        {"eid": event_id, "ek": entry_key},
    ).mappings().first()
    if not entry_row:
        raise HTTPException(status_code=400, detail="Invalid entry for this event")

    # Use canonical DB name so picks stay consistent even if client sends stale/mismatched text.
    entry_name = str(entry_row["entry_name"])

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
                "ek": entry_key,
                "en": entry_name,
            },
        ).mappings().first()

        db.commit()

    except Exception as e:
        db.rollback()

        msg = str(e).lower()

        # Turn common constraint failures into friendly messages
        if "uq_pick_user_per_event" in msg or ("unique" in msg and "user" in msg and "event" in msg):
            raise HTTPException(status_code=409, detail="You already picked for this event")
        if "uq_pick_no_dupe_entry" in msg or ("unique" in msg and "entry" in msg):
            raise HTTPException(status_code=409, detail="That entry was already drafted for this event")

        # Generic conflict (don't leak internals)
        raise HTTPException(status_code=409, detail="Pick rejected")

    return {"ok": True, "pick": dict(row), "state": _current_state(db, league_id)}
