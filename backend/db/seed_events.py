# backend/seed_events.py
"""
Seed public.events from backend/db/data/events.json
Uses DATABASE_URL (postgresql+psycopg://...)
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv


# Load .env
load_dotenv()

EVENTS_JSON_PATH = Path(__file__).resolve().parent / "data" / "events.json"


def require_env(name: str) -> str:
    val = os.getenv(name)
    if not val:
        raise RuntimeError(f"Missing required env var: {name}")
    return val


def main() -> None:
    if not EVENTS_JSON_PATH.exists():
        raise FileNotFoundError(f"events.json not found at: {EVENTS_JSON_PATH}")

    database_url = require_env("DATABASE_URL")

    events = json.loads(EVENTS_JSON_PATH.read_text(encoding="utf-8"))

    required = {"sport", "name", "event_key", "is_team_event", "sort_order"}
    for i, e in enumerate(events):
        missing = required - set(e.keys())
        if missing:
            raise RuntimeError(f"events[{i}] missing keys: {missing}")

    # psycopg does NOT like the SQLAlchemy-style prefix
    # Strip "+psycopg" if present
    database_url = database_url.replace("postgresql+psycopg://", "postgresql://")

    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            for e in events:
                cur.execute(
                    """
                    insert into public.events (
                        sport,
                        name,
                        event_key,
                        is_team_event,
                        sort_order
                    )
                    values (%s, %s, %s, %s, %s)
                    on conflict (event_key) do update
                    set
                        sport = excluded.sport,
                        name = excluded.name,
                        is_team_event = excluded.is_team_event,
                        sort_order = excluded.sort_order
                    """,
                    (
                        e["sport"],
                        e["name"],
                        e["event_key"],
                        e["is_team_event"],
                        e["sort_order"],
                    ),
                )

        conn.commit()

    print(f"Seeded {len(events)} events into public.events.")

    # quick sanity check
    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute("select count(*) from public.events;")
            count = cur.fetchone()[0]
            print(f"public.events now contains {count} rows.")


if __name__ == "__main__":
    main()
