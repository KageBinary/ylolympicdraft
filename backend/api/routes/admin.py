from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from api.deps import get_current_user
from core.config import settings
from db.session import get_db

router = APIRouter(prefix="/admin", tags=["admin"])


class GlobalResultRowIn(BaseModel):
    event_ref: str = Field(min_length=1, max_length=300)
    leaderboard: list[str] = Field(min_length=10, max_length=10)


class ImportGlobalResultsIn(BaseModel):
    admin_password: str | None = None
    rows: list[GlobalResultRowIn] = Field(min_length=1, max_length=500)


POINTS = {1: 8, 2: 5, 3: 3, 4: 1, 5: 1, 6: 1, 7: 1, 8: 1, 9: 1, 10: 1}


def _require_results_admin(user: dict, body_password: str | None) -> None:
    configured_user = settings.results_admin_username
    if not configured_user:
        raise HTTPException(status_code=500, detail="RESULTS_ADMIN_USERNAME is not configured")
    if user.get("username") != configured_user:
        raise HTTPException(status_code=403, detail="Global results admin only")

    configured_password = settings.results_admin_password
    if configured_password and (body_password or "") != configured_password:
        raise HTTPException(status_code=403, detail="Invalid admin password")


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


def _resolve_event_id(db: Session, event_ref: str) -> str:
    v = event_ref.strip()
    if not v:
        raise HTTPException(status_code=400, detail="Blank event_ref")

    by_id = db.execute(
        text("select id::text as id from public.events where id::text = :v"),
        {"v": v},
    ).mappings().first()
    if by_id:
        return str(by_id["id"])

    by_key = db.execute(
        text("select id::text as id from public.events where event_key = :v"),
        {"v": v},
    ).mappings().first()
    if by_key:
        return str(by_key["id"])

    by_name = db.execute(
        text(
            """
            select id::text as id
            from public.events
            where lower(name) = lower(:v)
            """
        ),
        {"v": v},
    ).mappings().all()
    if len(by_name) == 1:
        return str(by_name[0]["id"])
    if len(by_name) > 1:
        raise HTTPException(status_code=400, detail=f"Event name is ambiguous: {v}")

    raise HTTPException(status_code=400, detail=f"Event not found for event_ref: {v}")


def _resolve_entry_for_name(db: Session, event_id: str, athlete_name: str) -> tuple[str, str]:
    v = athlete_name.strip()
    if not v:
        raise HTTPException(status_code=400, detail="Leaderboard contains blank athlete name")

    rows = db.execute(
        text(
            """
            select entry_key, entry_name
            from public.event_entries
            where event_id = :eid
              and lower(entry_name) = lower(:name)
            """
        ),
        {"eid": event_id, "name": v},
    ).mappings().all()
    if len(rows) == 1:
        return str(rows[0]["entry_key"]), str(rows[0]["entry_name"])
    if len(rows) > 1:
        raise HTTPException(
            status_code=400,
            detail=f"Ambiguous athlete name '{v}' for event {event_id}. Use unique names.",
        )
    raise HTTPException(status_code=400, detail=f"Athlete name '{v}' not found for event {event_id}")


@router.post("/results/import-global")
def import_global_results(
    body: ImportGlobalResultsIn,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    _require_results_admin(user, body.admin_password)
    _ensure_global_results_table(db)

    imported_events = 0
    try:
        for row in body.rows:
            event_id = _resolve_event_id(db, row.event_ref)

            normalized_names = [n.strip() for n in row.leaderboard]
            if len(set(normalized_names)) != len(normalized_names):
                raise HTTPException(status_code=400, detail=f"Duplicate athlete names in event_ref '{row.event_ref}'")

            db.execute(
                text("delete from public.global_event_results where event_id = :eid"),
                {"eid": event_id},
            )

            for idx, athlete_name in enumerate(normalized_names, start=1):
                entry_key, entry_name = _resolve_entry_for_name(db, event_id, athlete_name)
                db.execute(
                    text(
                        """
                        insert into public.global_event_results
                          (event_id, place, entry_key, entry_name)
                        values
                          (:eid, :place, :ek, :en)
                        """
                    ),
                    {"eid": event_id, "place": idx, "ek": entry_key, "en": entry_name},
                )
            imported_events += 1

        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to import global results")

    return {"ok": True, "imported_events": imported_events, "points": POINTS}
