"""
Extract medal-event list from OLY.pdf and output backend/db/data/events.json

Run:
  pip install pymupdf
  python olyscrape.py
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from collections import Counter

import fitz  # PyMuPDF


# ---- PATHS ----
PDF_PATH = Path(__file__).resolve().parent.parent / "OLY.pdf"
OUT_PATH = Path(__file__).resolve().parent / "db" / "data" / "events.json"


# ---- SPORTS ----
SPORTS = {
    "Alpine Skiing",
    "Biathlon",
    "Bobsleigh",
    "Cross-Country Skiing",
    "Curling",
    "Figure Skating",
    "Freestyle Skiing",
    "Ice Hockey",
    "Luge",
    "Nordic Combined",
    "Short Track",
    "Ski Jumping",
    "Ski Mountaineering",
    "Skeleton",
    "Snowboard",
    "Speed Skating",
}


# ---- FILTERING RULES ----
DROP_CONTAINS = [
    "Qualification", "Qualifying",
    "Heat", "Heats",
    "Quarterfinal", "Quarterfinals",
    "Semifinal", "Semifinals",
    "Preliminary",
    "Round Robin",
    "Bronze Medal", "Gold Medal",
    "Run 1", "Run 2", "Run 3", "Run 4",
    "Total",
    "Park",
    "Livigno", "Cortina", "Milano", "Anterselva", "Predazzo", "Tesero",
]

DROP_EXACT = {
    "Women", "Men", "Mixed",
    "Final", "Finals",
    "Opening Ceremony", "Closing Ceremony",
    "&",
}

GENERIC_EVENT_WORDS = {
    "Downhill", "Slalom", "Giant Slalom", "Super-G",
    "Moguls", "Dual Moguls", "Aerials",
    "Slopestyle", "Halfpipe", "Big Air", "Ski Cross",
}

NEUTRAL_OK = {
    "Ice Dance",
    "Team Event",
    "Mixed Doubles",
}

TEAM_EVENT_KEYWORDS = ["team", "relay", "pairs", "pair", "doubles", "mixed", "tournament"]


# ---- HELPERS ----
def slugify(s: str) -> str:
    s = s.strip().lower()
    s = s.replace("&", "and")
    s = re.sub(r"[’'`]", "", s)
    s = re.sub(r"[^a-z0-9]+", "_", s)
    return re.sub(r"_+", "_", s).strip("_")


def is_team_event(sport: str, name: str) -> bool:
    x = f"{sport} {name}".lower()
    if sport in {"Ice Hockey", "Curling"}:
        return True
    return any(k in x for k in TEAM_EVENT_KEYWORDS)


def normalize(s: str) -> str:
    return s.replace("Women’s", "Women's").replace("Men’s", "Men's").replace("’", "'").strip()


def should_drop(name: str) -> bool:
    if not name or name in DROP_EXACT:
        return True
    for bad in DROP_CONTAINS:
        if bad.lower() in name.lower():
            return True
    if name.startswith("&"):
        return True
    if re.search(r"\b\d{1,2}:\d{2}\b", name):
        return True
    if re.fullmatch(r"[A-Z]{3}-[A-Z]{3}", name):
        return True
    if re.fullmatch(r"#\d+-#\d+", name.replace(" ", "")):
        return True
    return False


def extract_text(pdf_path: Path) -> str:
    doc = fitz.open(pdf_path)
    try:
        return "\n".join(page.get_text("text") for page in doc)
    finally:
        doc.close()


def stitch_lines(lines: list[str]) -> list[str]:
    out = []
    i = 0
    while i < len(lines):
        cur = normalize(lines[i])
        if not cur:
            i += 1
            continue

        # Expand "Women's and Men's X"
        if cur == "Women's and Men's" and i + 1 < len(lines):
            nxt = normalize(lines[i + 1])
            if nxt not in SPORTS:
                out.append(f"Women's {nxt}")
                out.append(f"Men's {nxt}")
                i += 2
                continue

        # Join split tokens
        if cur in {"Women's", "Men's", "Mixed"} or cur.endswith(("+", "-", "and", "–", "(")):
            if i + 1 < len(lines):
                nxt = normalize(lines[i + 1])
                if nxt not in SPORTS:
                    out.append(f"{cur} {nxt}")
                    i += 2
                    continue

        out.append(cur)
        i += 1
    return out


def looks_like_event(sport: str, name: str) -> bool:
    if name in NEUTRAL_OK:
        return True
    if re.search(r"\bMen'?s\b|\bWomen'?s\b|\bMixed\b", name):
        return True
    if sport == "Nordic Combined" and any(k in name for k in ["Individual", "Team Sprint", "Gundersen"]):
        return True
    return False


# ---- MAIN ----
def main():
    text = extract_text(PDF_PATH)
    lines = stitch_lines([normalize(l) for l in text.splitlines() if l.strip()])

    events = []
    seen = set()
    current_sport = None

    for line in lines:
        if line in SPORTS:
            current_sport = line
            continue
        if not current_sport:
            continue

        if line.startswith("Women's and Men's "):
            tail = line.replace("Women's and Men's ", "")
            for sex in ["Women's", "Men's"]:
                name = f"{sex} {tail}"
                if should_drop(name) or name in GENERIC_EVENT_WORDS:
                    continue
                key = f"{slugify(current_sport)}_{slugify(name)}"
                if key not in seen:
                    seen.add(key)
                    events.append({
                        "sport": current_sport,
                        "name": name,
                        "event_key": key,
                        "is_team_event": is_team_event(current_sport, name),
                    })
            continue

        if should_drop(line) or line in GENERIC_EVENT_WORDS:
            continue
        if not looks_like_event(current_sport, line):
            continue

        key = f"{slugify(current_sport)}_{slugify(line)}"
        if key in seen:
            continue
        seen.add(key)
        events.append({
            "sport": current_sport,
            "name": line,
            "event_key": key,
            "is_team_event": is_team_event(current_sport, line),
        })


    # ---- HARD NORMALIZATION (FINAL 116) ----
    def clear_sport(sport):
        nonlocal events, seen
        events = [e for e in events if e["sport"] != sport]
        seen = {e["event_key"] for e in events}

    def add(sport, name):
        key = f"{slugify(sport)}_{slugify(name)}"
        if key not in seen:
            seen.add(key)
            events.append({
                "sport": sport,
                "name": name,
                "event_key": key,
                "is_team_event": is_team_event(sport, name),
            })

    # Nordic Combined (3)
    clear_sport("Nordic Combined")
    add("Nordic Combined", "Men's Individual (Normal Hill)")
    add("Nordic Combined", "Men's Individual (Large Hill)")
    add("Nordic Combined", "Men's Team Sprint")

    # Curling (3)
    add("Curling", "Men's Tournament")
    add("Curling", "Women's Tournament")

    # Figure Skating (5)
    add("Figure Skating", "Men's Singles")
    add("Figure Skating", "Women's Singles")
    add("Figure Skating", "Pairs")
    add("Figure Skating", "Ice Dance")
    add("Figure Skating", "Team Event")

    # Bobsleigh (4)
    clear_sport("Bobsleigh")
    add("Bobsleigh", "Men's Two-man")
    add("Bobsleigh", "Women's Two-woman")
    add("Bobsleigh", "Men's Four-man")
    add("Bobsleigh", "Women's Monobob")

    # Skeleton (3)
    clear_sport("Skeleton")
    add("Skeleton", "Men's Singles")
    add("Skeleton", "Women's Singles")
    add("Skeleton", "Mixed Team")

    # Luge (5)
    clear_sport("Luge")
    add("Luge", "Men's Singles")
    add("Luge", "Women's Singles")
    add("Luge", "Men's Doubles")
    add("Luge", "Women's Doubles")
    add("Luge", "Team Relay")

    # Ice Hockey (2)
    clear_sport("Ice Hockey")
    add("Ice Hockey", "Men's Tournament")
    add("Ice Hockey", "Women's Tournament")

    # ---- FINAL ORDERING ----
    for i, e in enumerate(events, start=1):
        e["sort_order"] = i

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(events, indent=2), encoding="utf-8")

    print(f"Wrote {len(events)} events -> {OUT_PATH}")
    counts = Counter(e["sport"] for e in events)
    for s in sorted(counts):
        print(f"{s}: {counts[s]}")


if __name__ == "__main__":
    main()
