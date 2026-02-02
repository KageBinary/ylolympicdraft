"""
DEV RESET: deletes all league/user/draft/results data, keeps events.

What it wipes:
- league_event_results
- draft_picks
- league_members
- leagues
- users

What it keeps:
- events

Safety:
- Requires env var CONFIRM_RESET=YES to run.
"""

import os
from sqlalchemy import text
from db.session import engine


def main() -> None:
    confirm = os.getenv("CONFIRM_RESET", "")
    if confirm != "YES":
        raise SystemExit(
            "Refusing to reset without confirmation.\n"
            "Run like:\n"
            "  CONFIRM_RESET=YES python reset_dev.py\n"
        )

    # IMPORTANT: order matters because of foreign keys
    statements = [
        # Truncate is fastest + resets identities (if any). CASCADE handles FK dependencies among these tables.
        """
        truncate table
          public.league_event_results,
          public.draft_picks,
          public.league_members,
          public.leagues,
          public.users
        restart identity
        cascade;
        """
    ]

    with engine.begin() as conn:
        for sql in statements:
            conn.execute(text(sql))

    print("✅ Dev reset complete. Kept: public.events. Wiped: users/leagues/members/picks/results.")


if __name__ == "__main__":
    main()
