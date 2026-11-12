from datetime import date

from op_tracker.diff import diff
from op_tracker.rating import is_candidate, is_overwhelmingly_positive
from op_tracker.reasons import classify
from op_tracker.snapshot import entry_from_item, is_new_release
from op_tracker.steam import StoreItem, parse_item

RAW_STARDEW = {
    "id": 413150,
    "appid": 413150,
    "success": 1,
    "visible": True,
    "type": 0,
    "name": "Stardew Valley",
    "store_url_path": "app/413150/Stardew_Valley",
    "reviews": {
        "summary_filtered": {
            "review_count": 904542,
            "percent_positive": 98,
            "review_score": 9,
            "review_score_label": "Overwhelmingly Positive",
        }
    },
    "assets": {"asset_url_format": "steam/apps/413150/${FILENAME}?t=1", "header": "header.jpg"},
    "release": {"steam_release_date": 1456509578},
    "best_purchase_option": {"formatted_final_price": "$14.99"},
}

PREV = {"appid": 1, "name": "Game", "percent_positive": 96, "review_count": 1000}


def item(**kw) -> StoreItem:
    base = {
        "appid": 1,
        "found": True,
        "visible": True,
        "name": "Game",
        "app_type": 0,
        "review_score": 8,
        "review_label": "Very Positive",
        "percent_positive": 94,
        "review_count": 1100,
    }
    return StoreItem(**{**base, **kw})


# --- rating -------------------------------------------------------------------


def test_candidate_filter_has_buffer_around_real_thresholds():
    assert is_candidate(470, 30)  # 500 reviews, 94% -> near the line, keep
    assert is_candidate(380, 20)  # 400 reviews, 95%
    assert not is_candidate(300, 10)  # too few reviews
    assert not is_candidate(800, 200)  # 80%


def test_overwhelmingly_positive_uses_steam_score():
    assert is_overwhelmingly_positive(9)
    assert not is_overwhelmingly_positive(8)
    assert not is_overwhelmingly_positive(None)


# --- parsing ------------------------------------------------------------------


def test_parse_item_extracts_fields():
    it = parse_item(RAW_STARDEW)
    assert it.found and it.is_game
    assert it.review_label == "Overwhelmingly Positive" and it.percent_positive == 98
    assert it.header_image.endswith("steam/apps/413150/header.jpg?t=1")
    assert it.store_url == "https://store.steampowered.com/app/413150/Stardew_Valley"
    assert entry_from_item(it)["release_date"] == "2016-02-26"


def test_parse_item_missing_is_not_found():
    assert not parse_item({"id": 5, "success": 2}).found


def test_dlc_is_not_a_game():
    assert not parse_item({**RAW_STARDEW, "type": 11}).is_game


def test_new_release_window():
    today = date(2026, 11, 12)
    assert is_new_release({"release_date": "2026-10-01"}, today)
    assert not is_new_release({"release_date": "2025-01-01"}, today)
    assert not is_new_release({"release_date": None}, today)


# --- diff ---------------------------------------------------------------------


def test_diff_finds_new_and_dropped():
    prev = {1: {}, 2: {}, 3: {}}
    curr = {2: {}, 3: {}, 4: {}, 5: {}}
    assert diff(prev, curr) == ([4, 5], [1])


# --- reasons ------------------------------------------------------------------


def test_reason_delisted():
    assert classify(PREV, None)["code"] == "delisted"
    assert classify(PREV, item(found=False))["code"] == "delisted"
    assert classify(PREV, item(visible=False))["code"] == "delisted"


def test_reason_score_fell():
    r = classify(PREV, item(percent_positive=94))
    assert r["code"] == "score_fell"
    assert "96% to 94%" in r["detail"] and "Very Positive" in r["detail"]


def test_reason_reviews_removed():
    r = classify(PREV, item(percent_positive=96, review_count=480))
    assert r["code"] == "reviews_removed"


def test_reason_other():
    assert classify(PREV, item(percent_positive=95, review_count=1000))["code"] == (
        "rating_changed_other"
    )


def test_recent_negative_trend_is_mentioned():
    r = classify(PREV, item(percent_positive=94), recent_pct=60.0)
    assert r["recent_percent_positive"] == 60.0
    assert "60% of the most recent reviews" in r["detail"]


def test_recent_close_to_overall_not_mentioned():
    r = classify(PREV, item(percent_positive=94), recent_pct=90.0)
    assert "most recent" not in r["detail"]
