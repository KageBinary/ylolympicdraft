import json
from collections import Counter
from pathlib import Path

EVENTS_JSON = Path(__file__).resolve().parent / "data" / "events.json"

def main():
    events = json.loads(EVENTS_JSON.read_text(encoding="utf-8"))
    keys = [e["event_key"] for e in events]
    counts = Counter(keys)
    dups = [(k, c) for k, c in counts.items() if c > 1]

    if not dups:
        print("No duplicate event_key values in events.json")
        return

    print("Duplicate event_key values:")
    for k, c in sorted(dups, key=lambda x: (-x[1], x[0])):
        print(f"  {k}  (x{c})")

    # Print full entries for each duplicate key
    for k, _ in dups:
        print(f"\nEntries for {k}:")
        for e in events:
            if e["event_key"] == k:
                print(json.dumps(e, indent=2))

if __name__ == "__main__":
    main()
