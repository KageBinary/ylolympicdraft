from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text

from db.session import get_db
from api.deps import get_current_user

router = APIRouter(prefix="/events", tags=["events"])


def _require_member(db: Session, league_id: str, user_id: str) -> None:
    row = db.execute(
        text("select 1 from public.league_members where league_id=:lid and user_id=:uid"),
        {"lid": league_id, "uid": user_id},
    ).first()
    if not row:
        raise HTTPException(status_code=403, detail="Not a member of this league")


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
    return db.execute(
        text(
            """
            select
              p.id,
              p.user_id,
              u.username,
              p.entry_key,
              p.entry_name,
              p.picked_at
            from public.draft_picks p
            join public.users u on u.id = p.user_id
            where p.league_id = :lid and p.event_id = :eid
            order by p.picked_at asc
            """
        ),
        {"lid": league_id, "eid": event_id},
    ).mappings().all()


def _get_results_for_event(db: Session, league_id: str, event_id: str):
    return db.execute(
        text(
            """
            select place, entry_key, entry_name, created_at
            from public.league_event_results
            where league_id = :lid and event_id = :eid
            order by place asc
            """
        ),
        {"lid": league_id, "eid": event_id},
    ).mappings().all()


def _compute_draft_context(db: Session, league_id: str):
    """
    Lightweight version of draft state:
    - current_event_id (first event not fully drafted)
    - on_the_clock user (based on snake + picks count)
    If draft hasn't started (no draft_position), returns None.
    """
    members = _get_members_in_draft_order(db, league_id)
    if not members or members[0]["draft_position"] is None:
        return {"draft_started": False, "current_event_id": None, "on_the_clock": None}

    events = _get_events_in_order(db)
    n = len(members)

    for idx, ev in enumerate(events):
        picks = _get_picks_for_event(db, league_id, str(ev["id"]))
        if len(picks) < n:
            forward = (idx % 2 == 0)
            order = members if forward else list(reversed(members))
            on_the_clock = order[len(picks)]
            return {
                "draft_started": True,
                "current_event_id": str(ev["id"]),
                "current_event_index": idx,
                "direction": "forward" if forward else "reverse",
                "on_the_clock": {"id": str(on_the_clock["id"]), "username": on_the_clock["username"]},
            }

    return {"draft_started": True, "current_event_id": None, "on_the_clock": None, "complete": True}


@router.get("/")
def list_events(db: Session = Depends(get_db)):
    rows = db.execute(
        text(
            """
            select id, sport, name, event_key, is_team_event, sort_order
            from public.events
            order by sort_order asc
            """
        )
    ).mappings().all()

    return [
        {
            "id": str(r["id"]),
            "sport": r["sport"],
            "name": r["name"],
            "event_key": r["event_key"],
            "is_team_event": r["is_team_event"],
            "sort_order": r["sort_order"],
        }
        for r in rows
    ]


@router.get("/{event_id}")
def event_detail(event_id: str, db: Session = Depends(get_db)):
    row = db.execute(
        text(
            """
            select id, sport, name, event_key, is_team_event, sort_order
            from public.events
            where id = :eid
            """
        ),
        {"eid": event_id},
    ).mappings().first()

    if not row:
        raise HTTPException(status_code=404, detail="Event not found")

    return {
        "id": str(row["id"]),
        "sport": row["sport"],
        "name": row["name"],
        "event_key": row["event_key"],
        "is_team_event": row["is_team_event"],
        "sort_order": row["sort_order"],
    }


@router.get("/league/{league_id}/{event_id}/summary")
def event_summary_for_league(
    league_id: str,
    event_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    _require_member(db, league_id, user["id"])

    event = db.execute(
        text(
            """
            select id, sport, name, event_key, is_team_event, sort_order
            from public.events
            where id = :eid
            """
        ),
        {"eid": event_id},
    ).mappings().first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    picks = _get_picks_for_event(db, league_id, event_id)
    results = _get_results_for_event(db, league_id, event_id)

    draft_ctx = _compute_draft_context(db, league_id)

    return {
        "league_id": league_id,
        "event": {
            "id": str(event["id"]),
            "sport": event["sport"],
            "name": event["name"],
            "event_key": event["event_key"],
            "is_team_event": event["is_team_event"],
            "sort_order": event["sort_order"],
        },
        "picks": [
            {
                "user_id": str(p["user_id"]),
                "username": p["username"],
                "entry_key": p["entry_key"],
                "entry_name": p["entry_name"],
                "picked_at": p["picked_at"],
            }
            for p in picks
        ],
        "results": [
            {
                "place": r["place"],
                "entry_key": r["entry_key"],
                "entry_name": r["entry_name"],
                "created_at": r["created_at"],
            }
            for r in results
        ],
        "draft": draft_ctx,
    }
