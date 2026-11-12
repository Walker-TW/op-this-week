"""Client for Steam's official store API (IStoreBrowseService/GetItems).

One batched request returns, per app: name, app type, visibility, review summary
(label, % positive, count), release date and image assets.
"""

import json
import time
from dataclasses import dataclass

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

GET_ITEMS_URL = "https://api.steampowered.com/IStoreBrowseService/GetItems/v1/"
APP_REVIEWS_URL = "https://store.steampowered.com/appreviews/{appid}"
ASSET_BASE = "https://shared.akamai.steamstatic.com/store_item_assets/"
STORE_BASE = "https://store.steampowered.com/"

APP_TYPE_GAME = 0  # GetItems `type` field: 0 = game (DLC, music, software etc. are other values)
BATCH_SIZE = 100
USER_AGENT = "op-this-week/0.1 (weekly Steam review tracker)"


class SteamError(Exception):
    """Raised when Steam can't be reached reliably; the run must stop without writing data."""


@dataclass
class StoreItem:
    appid: int
    found: bool  # False = Steam returned no data (delisted / removed / never existed)
    visible: bool = False
    name: str = ""
    app_type: int | None = None
    review_score: int | None = None
    review_label: str | None = None
    percent_positive: int | None = None
    review_count: int | None = None
    release_ts: int | None = None
    header_image: str | None = None
    store_url: str | None = None
    price: str | None = None

    @property
    def is_game(self) -> bool:
        return self.app_type == APP_TYPE_GAME


def parse_item(raw: dict) -> StoreItem:
    appid = int(raw.get("appid") or raw.get("id"))
    if raw.get("success") != 1:
        return StoreItem(appid=appid, found=False)

    summary = (raw.get("reviews") or {}).get("summary_filtered") or {}
    assets = raw.get("assets") or {}
    header = None
    if assets.get("asset_url_format") and assets.get("header"):
        header = ASSET_BASE + assets["asset_url_format"].replace("${FILENAME}", assets["header"])

    release = raw.get("release") or {}
    price = None
    if raw.get("is_free"):
        price = "Free"
    elif raw.get("best_purchase_option"):
        price = raw["best_purchase_option"].get("formatted_final_price")

    return StoreItem(
        appid=appid,
        found=True,
        visible=bool(raw.get("visible")),
        name=raw.get("name", ""),
        app_type=raw.get("type"),
        review_score=summary.get("review_score"),
        review_label=summary.get("review_score_label"),
        percent_positive=summary.get("percent_positive"),
        review_count=summary.get("review_count"),
        release_ts=release.get("steam_release_date") or release.get("original_release_date"),
        header_image=header,
        store_url=STORE_BASE + raw["store_url_path"] if raw.get("store_url_path") else None,
        price=price,
    )


class SteamClient:
    def __init__(self, min_interval: float = 1.0, country: str = "US"):
        self._http = httpx.Client(timeout=30, headers={"User-Agent": USER_AGENT})
        self._min_interval = min_interval
        self._last_call = 0.0
        self._country = country

    def _throttle(self) -> None:
        wait = self._min_interval - (time.monotonic() - self._last_call)
        if wait > 0:
            time.sleep(wait)
        self._last_call = time.monotonic()

    @retry(
        retry=retry_if_exception_type((httpx.HTTPError, ValueError)),
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=2, max=60),
        reraise=True,
    )
    def _get_items_batch(self, appids: list[int]) -> list[dict]:
        self._throttle()
        payload = {
            "ids": [{"appid": a} for a in appids],
            "context": {"language": "english", "country_code": self._country},
            "data_request": {
                "include_reviews": True,
                "include_release": True,
                "include_assets": True,
            },
        }
        resp = self._http.get(GET_ITEMS_URL, params={"input_json": json.dumps(payload)})
        resp.raise_for_status()
        return resp.json()["response"].get("store_items", [])

    def get_items(self, appids: list[int]) -> dict[int, StoreItem]:
        """Fetch store data for all appids. Apps Steam omits are returned as found=False."""
        results: dict[int, StoreItem] = {}
        for i in range(0, len(appids), BATCH_SIZE):
            batch = appids[i : i + BATCH_SIZE]
            try:
                raw_items = self._get_items_batch(batch)
            except (httpx.HTTPError, ValueError, KeyError) as exc:
                raise SteamError(f"GetItems failed for batch starting {batch[0]}: {exc}") from exc
            for raw in raw_items:
                item = parse_item(raw)
                results[item.appid] = item
        for appid in appids:
            results.setdefault(appid, StoreItem(appid=appid, found=False))
        return results

    def recent_percent_positive(self, appid: int, count: int = 100) -> float | None:
        """% positive among the most recent reviews, or None if unavailable.

        Uses the store's appreviews endpoint, which may redirect for some clients;
        any failure just means we skip this extra detail.
        """
        self._throttle()
        try:
            resp = self._http.get(
                APP_REVIEWS_URL.format(appid=appid),
                params={
                    "json": 1,
                    "filter": "recent",
                    "language": "all",
                    "purchase_type": "all",
                    "num_per_page": count,
                },
            )
            if resp.status_code != 200:
                return None
            reviews = resp.json().get("reviews") or []
        except (httpx.HTTPError, ValueError):
            return None
        if not reviews:
            return None
        up = sum(1 for r in reviews if r.get("voted_up"))
        return round(100.0 * up / len(reviews), 1)

    def close(self) -> None:
        self._http.close()
