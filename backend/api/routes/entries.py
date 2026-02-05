from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text

from db.session import get_db
from api.deps import get_current_user

router = APIRouter(prefix="/entries", tags=["entries"])


@router.get("/for-event")
def entries_for_event(
    league_id: str,
    event_id: str,
    q: str | None = None,
    limit: int = 50,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    # require membership (same pattern as other routes)
    row = db.execute(
        text("select 1 from public.league_members where league_id=:lid and user_id=:uid"),
        {"lid": league_id, "uid": user["id"]},
    ).first()
    if not row:
        raise HTTPException(status_code=403, detail="Not a member of this league")

    event_row = db.execute(
        text("select is_team_event from public.events where id = :eid"),
        {"eid": event_id},
    ).mappings().first()
    if not event_row:
        raise HTTPException(status_code=404, detail="Event not found")

    required_is_team = bool(event_row["is_team_event"])
    limit = max(1, min(limit, 200))

    if q:
        rows = db.execute(
            text(
                """
                select id, event_id, entry_key, entry_name, country_code, is_team
                from public.event_entries
                where event_id = :eid
                  and is_team = :required_is_team
                  and (entry_name ilike :q or entry_key ilike :q)
                order by entry_name asc
                limit :lim
                """
            ),
            {"eid": event_id, "required_is_team": required_is_team, "q": f"%{q.strip()}%", "lim": limit},
        ).mappings().all()
    else:
        rows = db.execute(
            text(
                """
                select id, event_id, entry_key, entry_name, country_code, is_team
                from public.event_entries
                where event_id = :eid
                  and is_team = :required_is_team
                order by entry_name asc
                limit :lim
                """
            ),
            {"eid": event_id, "required_is_team": required_is_team, "lim": limit},
        ).mappings().all()

    return {"event_id": event_id, "entries": [dict(r) for r in rows]}
