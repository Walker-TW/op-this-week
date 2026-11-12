"""Candidate discovery from SteamSpy's bulk endpoint.

`request=all` returns ~1,000 apps per page (sorted by owners) with positive/negative
review counts. SteamSpy asks for at most 1 request per 60 seconds on this endpoint.
"""

import time
from collections.abc import Iterator

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from .rating import is_candidate
from .steam import USER_AGENT, SteamError

STEAMSPY_URL = "https://steamspy.com/api.php"
PAGE_INTERVAL_SECONDS = 61


@retry(
    retry=retry_if_exception_type((httpx.HTTPError, ValueError, TypeError)),
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=30, max=180),
    reraise=True,
)
def _fetch_page(http: httpx.Client, page: int) -> dict:
    resp = http.get(STEAMSPY_URL, params={"request": "all", "page": page})
    resp.raise_for_status()
    data = resp.json()
    if not isinstance(data, dict):
        raise TypeError(f"unexpected SteamSpy response type: {type(data)}")
    return data


def iter_pages(max_pages: int | None = None) -> Iterator[dict]:
    """Yield each page's {appid: app} dict until SteamSpy returns an empty page."""
    with httpx.Client(timeout=60, headers={"User-Agent": USER_AGENT}) as http:
        page = 0
        while max_pages is None or page < max_pages:
            if page:
                time.sleep(PAGE_INTERVAL_SECONDS)
            try:
                data = _fetch_page(http, page)
            except (httpx.HTTPError, ValueError, TypeError) as exc:
                raise SteamError(f"SteamSpy page {page} failed: {exc}") from exc
            if not data:
                return
            yield data
            page += 1


def find_candidates(max_pages: int | None = None, log=print) -> set[int]:
    candidates: set[int] = set()
    for page_num, page in enumerate(iter_pages(max_pages)):
        for app in page.values():
            pos, neg = int(app.get("positive") or 0), int(app.get("negative") or 0)
            if is_candidate(pos, neg):
                candidates.add(int(app["appid"]))
        log(f"  SteamSpy page {page_num}: {len(page)} apps, {len(candidates)} candidates so far")
    return candidates
