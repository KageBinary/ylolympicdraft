from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, conint
from sqlalchemy.orm import Session
from sqlalchemy import text

from db.session import get_db
from api.deps import get_current_user

router = APIRouter(prefix="/results", tags=["results"])


# Global scoring for places 1..10
POINTS = {1: 8, 2: 5, 3: 3, 4: 1, 5: 1, 6: 1, 7: 1, 8: 1, 9: 1, 10: 1}
MAX_PLACE = max(POINTS.keys())


class PlacementIn(BaseModel):
    place: conint(ge=1, le=MAX_PLACE)  # type: ignore
    entry_key: str = Field(min_length=1, max_length=200)
    entry_name: str = Field(min_length=1, max_length=200)


class SubmitResultsIn(BaseModel):
    league_id: str
    event_id: str
    placements: list[PlacementIn]


def _require_member(db: Session, league_id: str, user_id: str) -> None:
    row = db.execute(
        text(
            """
            select 1
            from public.league_members
            where league_id=:lid and user_id=:uid
            """
        ),
        {"lid": league_id, "uid": user_id},
    ).first()
    if not row:
        raise HTTPException(status_code=403, detail="Not a member of this league")


def _require_commissioner(db: Session, league_id: str, user_id: str) -> None:
    row = db.execute(
        text("select commissioner_id from public.leagues where id=:lid"),
        {"lid": league_id},
    ).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="League not found")
    if str(row["commissioner_id"]) != str(user_id):
        raise HTTPException(status_code=403, detail="Commissioner only")


def _require_locked(db: Session, league_id: str) -> None:
    row = db.execute(
        text("select status from public.leagues where id=:lid"),
        {"lid": league_id},
    ).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="League not found")
    if row["status"] != "locked":
        raise HTTPException(status_code=409, detail=f"League not locked (status: {row['status']})")


def _ensure_global_results_table(db: Session) -> None:
    db.execute(
        text(
            """
            create table if not exists public.global_event_results (
              id uuid primary key default gen_random_uuid(),
              event_id uuid not null references public.events(id),
              place int not null,
              entry_key text not null,
              entry_name text not null,
              created_at timestamptz not null default now(),
              unique (event_id, place),
              unique (event_id, entry_key)
            )
            """
        )
    )


@router.post("/submit")
def submit_results(
    body: SubmitResultsIn,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    raise HTTPException(
        status_code=410,
        detail="Per-league submit is disabled. Use /admin/results/import-global (results admin only).",
    )


@router.get("/event")
def get_event_results(
    league_id: str,
    event_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    _require_member(db, league_id, user["id"])
    _ensure_global_results_table(db)

    rows = db.execute(
        text(
            """
            select place, entry_key, entry_name, created_at
            from public.global_event_results
            where event_id=:eid
            order by place asc
            """
        ),
        {"eid": event_id},
    ).mappings().all()

    return {"league_id": league_id, "event_id": event_id, "placements": [dict(r) for r in rows]}


@router.get("/leaderboard")
def leaderboard(
    league_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    _require_member(db, league_id, user["id"])
    _ensure_global_results_table(db)

    # points = sum over picks that match results by (league,event,entry_key)
    rows = db.execute(
        text(
            """
            select
              u.id as user_id,
              u.username as username,
              coalesce(sum(
                case r.place
                  when 1 then 8
                  when 2 then 5
                  when 3 then 3
                  when 4 then 1
                  when 5 then 1
                  when 6 then 1
                  when 7 then 1
                  when 8 then 1
                  when 9 then 1
                  when 10 then 1
                  else 0
                end
              ), 0) as points
            from public.league_members m
            join public.users u
              on u.id = m.user_id
            left join public.draft_picks p
              on p.league_id = m.league_id
             and p.user_id = m.user_id
            left join public.global_event_results r
              on r.event_id = p.event_id
              and r.entry_key = p.entry_key
            where m.league_id = :lid
            group by u.id, u.username
            order by points desc, u.username asc
            """
        ),
        {"lid": league_id},
    ).mappings().all()

    return {"league_id": league_id, "scoring": POINTS, "rows": [dict(r) for r in rows]}
