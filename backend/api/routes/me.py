from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text

from api.deps import get_current_user
from db.session import get_db

router = APIRouter(tags=["me"])


@router.get("/me")
def me(user=Depends(get_current_user)):
    return user


@router.get("/me/picks")
def my_picks(
    league_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    # Must be a member of the league
    is_member = db.execute(
        text(
            """
            select 1
            from public.league_members
            where league_id = :lid and user_id = :uid
            """
        ),
        {"lid": league_id, "uid": user["id"]},
    ).first()

    if not is_member:
        raise HTTPException(status_code=403, detail="Not a member of this league")

    rows = db.execute(
        text(
            """
            select
              e.id as event_id,
              e.sort_order,
              e.sport,
              e.name as event_name,
              p.entry_key,
              p.entry_name,
              p.picked_at
            from public.draft_picks p
            join public.events e on e.id = p.event_id
            where p.league_id = :lid and p.user_id = :uid
            order by e.sort_order asc
            """
        ),
        {"lid": league_id, "uid": user["id"]},
    ).mappings().all()

    return {
        "league_id": league_id,
        "user_id": user["id"],
        "picks": [dict(r) for r in rows],
    }
