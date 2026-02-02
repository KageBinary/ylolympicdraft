import os
import sys
import time
import random
import requests

BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:8000").rstrip("/")
EVENTS_TO_DRAFT = int(os.getenv("EVENTS_TO_DRAFT", "2"))  # how many events to draft in this test
SEED = int(os.getenv("SEED", "42"))  # deterministic randomness for entry names/keys

# If you already created these usernames before, change the prefix
USER_PREFIX = os.getenv("USER_PREFIX", "smoke")


def req(method: str, path: str, token: str | None = None, **kwargs):
    url = f"{BASE_URL}{path}"
    headers = kwargs.pop("headers", {})
    if token:
        headers["Authorization"] = f"Bearer {token}"
    r = requests.request(method, url, headers=headers, timeout=20, **kwargs)
    if r.status_code >= 400:
        # Helpful debug output
        try:
            body = r.json()
        except Exception:
            body = r.text
        raise RuntimeError(f"{method} {path} -> {r.status_code}: {body}")
    return r


def register_or_login(username: str, password: str) -> str:
    # Try register; if conflict, login
    try:
        r = req("POST", "/auth/register", json={"username": username, "password": password})
        return r.json()["access_token"]
    except RuntimeError as e:
        if "409" not in str(e) and "Username already taken" not in str(e):
            # not the expected "already exists"
            pass
        r = req("POST", "/auth/login", json={"username": username, "password": password})
        return r.json()["access_token"]


def create_league(token: str, name: str) -> dict:
    r = req("POST", "/leagues/create", token=token, json={"name": name})
    return r.json()


def join_league(token: str, code: str) -> dict:
    r = req("POST", "/leagues/join", token=token, json={"code": code})
    return r.json()


def start_draft(token: str, league_id: str) -> dict:
    r = req("POST", f"/leagues/{league_id}/start", token=token)
    return r.json()


def lock_league(token: str, league_id: str) -> dict:
    r = req("POST", f"/leagues/{league_id}/lock", token=token)
    return r.json()


def list_events() -> list[dict]:
    r = req("GET", "/events/")
    return r.json()


def draft_state(token: str, league_id: str) -> dict:
    r = req("GET", f"/draft/state?league_id={league_id}", token=token)
    return r.json()


def make_pick(token: str, league_id: str, entry_key: str, entry_name: str) -> dict:
    r = req(
        "POST",
        "/draft/pick",
        token=token,
        json={
            "league_id": league_id,
            "entry_key": entry_key,
            "entry_name": entry_name,
        },
    )
    return r.json()


def submit_results(token: str, league_id: str, event_id: str, placements: list[dict]) -> dict:
    r = req(
        "POST",
        "/results/submit",
        token=token,
        json={"league_id": league_id, "event_id": event_id, "placements": placements},
    )
    return r.json()


def leaderboard(token: str, league_id: str) -> dict:
    r = req("GET", f"/results/leaderboard?league_id={league_id}", token=token)
    return r.json()


def main():
    random.seed(SEED)

    # --- Create 4 users ---
    users = []
    for i in range(1, 5):
        username = f"{USER_PREFIX}{i}"
        password = "password123"
        token = register_or_login(username, password)
        users.append({"username": username, "token": token})

    commissioner = users[0]
    print(f"✅ Logged in users: {[u['username'] for u in users]}")

    # --- Create league ---
    league = create_league(commissioner["token"], name="Smoke Test League")
    league_id = league["id"]
    code = league["code"]
    print(f"✅ League created: id={league_id} code={code}")

    # --- Join league (users 2-4) ---
    for u in users[1:]:
        join_league(u["token"], code)
    print("✅ All users joined league")

    # --- Start draft ---
    start = start_draft(commissioner["token"], league_id)
    draft_order = start["draft_order"]
    print("✅ Draft started. Draft order:")
    for row in draft_order:
        print(f"   pos {row['draft_position']}: {row['username']}")

    # --- Fetch events ---
    events = list_events()
    if not events:
        raise RuntimeError("No events returned from /events/")
    events_to_draft = events[:EVENTS_TO_DRAFT]
    print(f"✅ Will draft first {len(events_to_draft)} events")

    # Map username->token for quick access
    token_by_username = {u["username"]: u["token"] for u in users}

    # --- Draft loop (event-by-event, snake handled by backend) ---
    # We'll generate unique entry_key per pick, and rely on backend to enforce turn order.
    used_keys_by_event = {}

    for ev_index in range(len(events_to_draft)):
        # Keep picking until backend advances to next event or draft complete
        while True:
            state = draft_state(commissioner["token"], league_id)

            if state.get("complete"):
                print("✅ Draft complete early")
                break

            current_event = state["event"]
            current_event_id = current_event["id"]

            # If we've moved past the event we intended, break to next
            target_event_id = events_to_draft[ev_index]["id"]
            if current_event_id != target_event_id:
                break

            otc = state["on_the_clock"]["username"]
            otc_token = token_by_username[otc]

            used = used_keys_by_event.setdefault(current_event_id, set())
            # create unique entry key
            # (you can change the format later to match real athlete/country IDs)
            while True:
                entry_key = f"EV{ev_index+1}-P{len(used)+1}-X{random.randint(1000,9999)}"
                if entry_key not in used:
                    used.add(entry_key)
                    break

            entry_name = f"Test Entry {entry_key}"

            make_pick(otc_token, league_id, entry_key, entry_name)
            print(f"✅ Pick made: event={current_event['sort_order']} on_clock={otc} -> {entry_name}")

        print(f"✅ Finished drafting event index {ev_index} ({events_to_draft[ev_index]['name']})")

    # --- Lock league (so results submission is allowed) ---
    lock_league(commissioner["token"], league_id)
    print("✅ League locked")

    # --- Submit results for the first drafted event ---
    first_event_id = events_to_draft[0]["id"]

    # For results, we’ll use the entries that were actually drafted for that event first,
    # then fill remaining places with dummy entries if fewer than 8 picks exist.
    # Get picks for that event via /events/league/.../summary if available; otherwise infer from draft state isn't enough.
    summary = req(
        "GET",
        f"/events/league/{league_id}/{first_event_id}/summary",
        token=commissioner["token"],
    ).json()

    picks = summary.get("picks", [])
    placements = []
    # Put drafted entries at top positions first
    place = 1
    for p in picks[:8]:
        placements.append(
            {"place": place, "entry_key": p["entry_key"], "entry_name": p["entry_name"]}
        )
        place += 1

    # Fill remaining places with dummy entries if needed
    while place <= 8:
        ek = f"RESULT-DUMMY-{place}-{random.randint(1000,9999)}"
        placements.append({"place": place, "entry_key": ek, "entry_name": f"Dummy {ek}"})
        place += 1

    submit_results(commissioner["token"], league_id, first_event_id, placements)
    print("✅ Results submitted for first event")

    # --- Leaderboard ---
    lb = leaderboard(commissioner["token"], league_id)
    print("\n🏅 Leaderboard")
    for row in lb["rows"]:
        print(f"  {row['username']}: {row['points']}")

    print("\n✅ Smoke test complete!")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("\n❌ Smoke test failed:")
        print(e)
        sys.exit(1)
