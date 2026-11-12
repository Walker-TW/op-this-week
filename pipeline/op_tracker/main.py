"""Weekly run: discover candidates, verify with Steam, diff against last week, write data.

Usage:
    uv run python -m op_tracker.main                       # full run (~1.5-2 h, SteamSpy-bound)
    uv run python -m op_tracker.main --max-pages 2 --dry-run   # quick smoke test
    uv run python -m op_tracker.main --appids 413150,730 --dry-run
"""

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

from . import steamspy
from .diff import diff
from .rating import is_overwhelmingly_positive
from .reasons import classify
from .snapshot import DATA_DIR, DataStore, entry_from_item, is_new_release
from .steam import SteamClient, SteamError

# If the list shrinks by more than this fraction in one week, assume a bad run and stop.
MAX_DROP_FRACTION = 0.2


def run(args: argparse.Namespace) -> int:
    now = datetime.now(UTC)
    week = now.date().isoformat()
    store = DataStore(Path(args.data_dir))
    previous = store.load_current()
    prev_games: dict[int, dict] = {g["appid"]: g for g in (previous or {}).get("games", [])}
    print(f"Run {week}: previous list has {len(prev_games)} games")

    # 1. Candidates
    if args.appids:
        candidates = {int(a) for a in args.appids.split(",")}
        print(f"Using {len(candidates)} appids from --appids")
    else:
        print("Discovering candidates from SteamSpy...")
        candidates = steamspy.find_candidates(max_pages=args.max_pages)
    # Always re-check last week's games so drop-outs are confirmed, not inferred.
    to_check = sorted(candidates | set(prev_games))
    print(f"Verifying {len(to_check)} apps with Steam...")

    # 2. Verify with Steam
    client = SteamClient()
    try:
        items = client.get_items(to_check)

        current_games: dict[int, dict] = {
            appid: entry_from_item(item)
            for appid, item in items.items()
            if item.found
            and item.visible
            and item.is_game
            and is_overwhelmingly_positive(item.review_score)
        }
        print(f"Overwhelmingly Positive games found: {len(current_games)}")

        # 3. Diff
        new_ids, dropped_ids = ([], []) if previous is None else diff(prev_games, current_games)
        if previous is None:
            print("First run: saving a baseline (nothing reported as new or dropped).")

        partial_run = bool(args.appids or args.max_pages)
        if (
            prev_games
            and not partial_run
            and not args.force
            and len(dropped_ids) > MAX_DROP_FRACTION * len(prev_games)
        ):
            print(
                f"ABORT: {len(dropped_ids)} of {len(prev_games)} games would drop out. "
                "This looks like a bad run; nothing written. Use --force to override.",
                file=sys.stderr,
            )
            return 2

        dropped = []
        for appid in dropped_ids:
            item = items.get(appid)
            recent = client.recent_percent_positive(appid) if item and item.found else None
            dropped.append(
                {
                    "before": prev_games[appid],
                    "now": entry_from_item(item) if item and item.found else None,
                    "reason": classify(prev_games[appid], item, recent),
                }
            )
    finally:
        client.close()

    new_entries = [
        {**current_games[a], "is_new_release": is_new_release(current_games[a], now.date())}
        for a in new_ids
    ]

    games_sorted = sorted(
        current_games.values(), key=lambda g: (-(g["review_count"] or 0), g["name"])
    )
    snapshot = {
        "week": week,
        "generated_at": now.isoformat(),
        "count": len(games_sorted),
        "games": games_sorted,
    }
    changes = {
        "week": week,
        "previous_week": (previous or {}).get("week"),
        "total": len(games_sorted),
        "new_entries": sorted(new_entries, key=lambda g: -(g["review_count"] or 0)),
        "dropped": dropped,
    }

    print(f"New this week: {len(new_entries)}   Dropped: {len(dropped)}")
    for g in new_entries:
        tag = " [new release]" if g["is_new_release"] else ""
        print(f"  + {g['name']} ({g['percent_positive']}%, {g['review_count']} reviews){tag}")
    for d in dropped:
        print(f"  - {d['before']['name']}: {d['reason']['detail']}")

    if args.dry_run:
        print("Dry run: nothing written.")
    else:
        store.write(week, snapshot, changes)
        print(f"Wrote data to {store.root}")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("--appids", help="comma-separated appids to check instead of SteamSpy discovery")
    p.add_argument("--max-pages", type=int, help="only read this many SteamSpy pages (testing)")
    p.add_argument("--dry-run", action="store_true", help="print results, write nothing")
    p.add_argument("--force", action="store_true", help="write even if many games dropped out")
    p.add_argument("--data-dir", default=str(DATA_DIR), help="where to read/write JSON data")
    args = p.parse_args(argv)
    try:
        return run(args)
    except SteamError as exc:
        print(f"ABORT: {exc}. Nothing written.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
