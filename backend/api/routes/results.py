from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, conint
from sqlalchemy.orm import Session
from sqlalchemy import text

from db.session import get_db
from api.deps import get_current_user

router = APIRouter(prefix="/results", tags=["results"])


# Deterministic scoring for places 1..8
POINTS = {1: 10, 2: 8, 3: 6, 4: 5, 5: 4, 6: 3, 7: 2, 8: 1}


class PlacementIn(BaseModel):
    place: conint(ge=1, le=8)  # type: ignore
    entry_key: str = Field(min_length=1, max_length=200)
    entry_name: str = Field(min_length=1, max_length=200)


class SubmitResultsIn(BaseModel):
    league_id: str
    event_id: str
    placements: list[PlacementIn]  # must include 1..8 exactly


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


@router.post("/submit")
def submit_results(
    body: SubmitResultsIn,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    _require_commissioner(db, body.league_id, user["id"])
    _require_locked(db, body.league_id)

    if len(body.placements) != 8:
        raise HTTPException(status_code=400, detail="Provide exactly 8 placements (1..8)")

    places = sorted([int(p.place) for p in body.placements])
    if places != [1, 2, 3, 4, 5, 6, 7, 8]:
        raise HTTPException(status_code=400, detail="Placements must be exactly places 1..8")

    # Prevent duplicates in payload itself
    entry_keys = [p.entry_key.strip() for p in body.placements]
    if len(set(entry_keys)) != 8:
        raise HTTPException(status_code=400, detail="Placements contain duplicate entry_key")

    # Replace results for (league,event)
    try:
        db.execute(
            text(
                """
                delete from public.league_event_results
                where league_id=:lid and event_id=:eid
                """
            ),
            {"lid": body.league_id, "eid": body.event_id},
        )

        for p in body.placements:
            db.execute(
                text(
                    """
                    insert into public.league_event_results
                      (league_id, event_id, place, entry_key, entry_name)
                    values
                      (:lid, :eid, :place, :ek, :en)
                    """
                ),
                {
                    "lid": body.league_id,
                    "eid": body.event_id,
                    "place": int(p.place),
                    "ek": p.entry_key.strip(),
                    "en": p.entry_name.strip(),
                },
            )

        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=409, detail="Failed to submit results (duplicate place/entry?)")

    return {"ok": True}


@router.get("/event")
def get_event_results(
    league_id: str,
    event_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    _require_member(db, league_id, user["id"])

    rows = db.execute(
        text(
            """
            select place, entry_key, entry_name, created_at
            from public.league_event_results
            where league_id=:lid and event_id=:eid
            order by place asc
            """
        ),
        {"lid": league_id, "eid": event_id},
    ).mappings().all()

    return {"league_id": league_id, "event_id": event_id, "placements": [dict(r) for r in rows]}


@router.get("/leaderboard")
def leaderboard(
    league_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    _require_member(db, league_id, user["id"])

    # points = sum over picks that match results by (league,event,entry_key)
    rows = db.execute(
        text(
            """
            select
              u.id as user_id,
              u.username as username,
              coalesce(sum(
                case r.place
                  when 1 then 10
                  when 2 then 8
                  when 3 then 6
                  when 4 then 5
                  when 5 then 4
                  when 6 then 3
                  when 7 then 2
                  when 8 then 1
                  else 0
                end
              ), 0) as points
            from public.league_members m
            join public.users u
              on u.id = m.user_id
            left join public.draft_picks p
              on p.league_id = m.league_id
             and p.user_id = m.user_id
            left join public.league_event_results r
              on r.league_id = p.league_id
             and r.event_id = p.event_id
             and r.entry_key = p.entry_key
            where m.league_id = :lid
            group by u.id, u.username
            order by points desc, u.username asc
            """
        ),
        {"lid": league_id},
    ).mappings().all()

    return {"league_id": league_id, "scoring": POINTS, "rows": [dict(r) for r in rows]}
