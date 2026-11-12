"""Steam review-score rules.

Steam labels a game "Overwhelmingly Positive" when it has 500+ reviews and 95%+ of them
are positive. Steam's API gives us the label directly (review_score == 9), so that is the
source of truth. The thresholds are still used to pick *candidates* from SteamSpy's bulk
data, with a buffer because SteamSpy's counts lag behind Steam's.
"""

OP_MIN_REVIEWS = 500
OP_MIN_PCT = 95
OVERWHELMINGLY_POSITIVE_SCORE = 9  # Steam's numeric review_score for the label

# Looser than the real thresholds so games near the line aren't missed.
CANDIDATE_MIN_REVIEWS = 400
CANDIDATE_MIN_PCT = 90


def percent_positive(positive: int, negative: int) -> float:
    total = positive + negative
    return 100.0 * positive / total if total else 0.0


def is_candidate(positive: int, negative: int) -> bool:
    """Could this app plausibly be Overwhelmingly Positive? (Used on SteamSpy data.)"""
    total = positive + negative
    return (
        total >= CANDIDATE_MIN_REVIEWS and percent_positive(positive, negative) >= CANDIDATE_MIN_PCT
    )


def is_overwhelmingly_positive(review_score: int | None) -> bool:
    return review_score == OVERWHELMINGLY_POSITIVE_SCORE
