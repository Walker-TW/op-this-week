"""Explain why a game dropped off the Overwhelmingly Positive list."""

from .rating import OP_MIN_PCT, OP_MIN_REVIEWS
from .steam import StoreItem

# Recent reviews this many points below the all-time score count as a negative trend.
RECENT_DROP_THRESHOLD = 10


def classify(prev: dict, now: StoreItem | None, recent_pct: float | None = None) -> dict:
    """Return {"code", "detail", "recent_percent_positive"?, "summary"?} for a dropped game."""
    if now is None or not now.found or not now.visible:
        return {
            "code": "delisted",
            "detail": "No longer available on the Steam store (delisted or removed).",
        }

    before_pct, after_pct = prev.get("percent_positive"), now.percent_positive
    before_n, after_n = prev.get("review_count"), now.review_count
    label = now.review_label or "unknown"

    if after_pct is not None and after_pct < OP_MIN_PCT:
        reason = {
            "code": "score_fell",
            "detail": f"Positive reviews fell from {before_pct}% to {after_pct}% "
            f"(now rated {label}).",
        }
    elif after_n is not None and after_n < OP_MIN_REVIEWS:
        reason = {
            "code": "reviews_removed",
            "detail": f"Review count fell from {before_n} to {after_n}, below the 500 needed "
            f"(now rated {label}).",
        }
    else:
        reason = {
            "code": "rating_changed_other",
            "detail": f"Steam now rates it {label} ({after_pct}% of {after_n} reviews).",
        }

    if recent_pct is not None:
        reason["recent_percent_positive"] = recent_pct
        if after_pct is not None and recent_pct <= after_pct - RECENT_DROP_THRESHOLD:
            reason["detail"] += f" Only {recent_pct:g}% of the most recent reviews are positive."

    summary = summarize(prev["appid"])
    if summary:
        reason["summary"] = summary
    return reason


def summarize(appid: int) -> str | None:
    """Phase 3 hook: AI summary of recent negative reviews.

    Will call Claude only when ANTHROPIC_API_KEY is set. Not implemented yet.
    """
    return None
