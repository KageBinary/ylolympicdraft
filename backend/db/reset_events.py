# backend/db/reset_events.py
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

from sqlalchemy import text
from db.session import engine


EVENTS_JSON_PATH = Path(__file__).resolve().parent / "data" / "events.json"


def _load_events(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"events.json not found at: {path}")

    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError("events.json must be a list of event objects")

    # Basic validation + normalize expected keys
    cleaned: List[Dict[str, Any]] = []
    for i, ev in enumerate(data):
        if not isinstance(ev, dict):
            raise ValueError(f"events.json item {i} is not an object")

        # Required fields (adjust if your JSON uses different keys)
        sport = ev.get("sport")
        name = ev.get("name")
        event_key = ev.get("event_key")
        is_team_event = ev.get("is_team_event", False)
        sort_order = ev.get("sort_order")

        if not sport or not name or not event_key or sort_order is None:
            raise ValueError(
                f"events.json item {i} missing required fields. "
                f"Need sport,name,event_key,sort_order. Got: {ev}"
            )

        cleaned.append(
            {
                "sport": str(sport),
                "name": str(name),
                "event_key": str(event_key),
                "is_team_event": bool(is_team_event),
                "sort_order": int(sort_order),
            }
        )

    # Uniqueness checks (helps catch silent partial loads later)
    keys = [e["event_key"] for e in cleaned]
    if len(keys) != len(set(keys)):
        raise ValueError("Duplicate event_key found in events.json")

    orders = [e["sort_order"] for e in cleaned]
    if len(orders) != len(set(orders)):
        raise ValueError("Duplicate sort_order found in events.json")

    return cleaned


def reset_and_seed_events() -> Tuple[int, int]:
    """
    Deletes events + dependent rows, then seeds events from db/data/events.json.
    Returns: (deleted_events_count, inserted_events_count)
    """
    events = _load_events(EVENTS_JSON_PATH)

    with engine.begin() as conn:
        # Count existing (just for reporting)
        old_count = conn.execute(text("select count(*) as c from public.events")).mappings().first()["c"]

        # Delete dependent tables first (FK-safe order)
        # Note: include league_events because it references events.
        conn.execute(text("delete from public.league_events"))
        conn.execute(text("delete from public.draft_picks"))
        conn.execute(text("delete from public.league_event_results"))
        conn.execute(text("delete from public.event_entries"))

        # Now delete events
        conn.execute(text("delete from public.events"))

        # Insert fresh events
        conn.execute(
            text(
                """
                insert into public.events (sport, name, event_key, is_team_event, sort_order)
                values (:sport, :name, :event_key, :is_team_event, :sort_order)
                """
            ),
            events,
        )

        new_count = conn.execute(text("select count(*) as c from public.events")).mappings().first()["c"]

    return int(old_count), int(new_count)


def main() -> None:
    print(f"📦 Loading events from: {EVENTS_JSON_PATH}")
    old_count, new_count = reset_and_seed_events()
    print(f"🧹 Deleted events: {old_count}")
    print(f"✅ Inserted events: {new_count}")


if __name__ == "__main__":
    main()
