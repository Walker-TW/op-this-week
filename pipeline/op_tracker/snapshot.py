"""Snapshot entries and the JSON files the site reads."""

import json
from datetime import UTC, date, datetime
from pathlib import Path

from .steam import StoreItem

DATA_DIR = Path(__file__).resolve().parents[2] / "data"


def entry_from_item(item: StoreItem) -> dict:
    release = (
        datetime.fromtimestamp(item.release_ts, UTC).date().isoformat() if item.release_ts else None
    )
    return {
        "appid": item.appid,
        "name": item.name,
        "percent_positive": item.percent_positive,
        "review_count": item.review_count,
        "review_label": item.review_label,
        "release_date": release,
        "header_image": item.header_image,
        "store_url": item.store_url or f"https://store.steampowered.com/app/{item.appid}/",
        "price": item.price,
    }


def is_new_release(entry: dict, today: date, days: int = 90) -> bool:
    if not entry.get("release_date"):
        return False
    return (today - date.fromisoformat(entry["release_date"])).days <= days


class DataStore:
    def __init__(self, root: Path = DATA_DIR):
        self.root = root

    @property
    def current_path(self) -> Path:
        return self.root / "current.json"

    def load_current(self) -> dict | None:
        if not self.current_path.exists():
            return None
        return json.loads(self.current_path.read_text())

    def write(self, week: str, snapshot: dict, changes: dict) -> None:
        (self.root / "snapshots").mkdir(parents=True, exist_ok=True)
        (self.root / "changes").mkdir(parents=True, exist_ok=True)
        _write_json(self.root / "snapshots" / f"{week}.json", snapshot)
        _write_json(self.root / "changes" / f"{week}.json", changes)
        _write_json(self.root / "latest_changes.json", changes)
        # Written last: current.json only changes once everything else succeeded.
        _write_json(self.current_path, snapshot)


def _write_json(path: Path, data: dict) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n")
    tmp.replace(path)
