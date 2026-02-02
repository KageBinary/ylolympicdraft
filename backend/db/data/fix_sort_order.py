import json
from pathlib import Path

EVENTS_PATH = Path(__file__).parent / "events.json"

def main():
    events = json.loads(EVENTS_PATH.read_text(encoding="utf-8"))

    # Sort by sport, then name (stable & predictable for UI)
    events.sort(key=lambda e: (e["sport"], e["name"]))

    # Reassign sort_order sequentially
    for i, e in enumerate(events, start=1):
        e["sort_order"] = i

    EVENTS_PATH.write_text(
        json.dumps(events, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    print(f"Reordered {len(events)} events successfully.")

if __name__ == "__main__":
    main()
