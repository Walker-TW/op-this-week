"""Compare last week's list with this week's."""


def diff(previous: dict[int, dict], current: dict[int, dict]) -> tuple[list[int], list[int]]:
    """Return (new_appids, dropped_appids), each sorted."""
    new = sorted(set(current) - set(previous))
    dropped = sorted(set(previous) - set(current))
    return new, dropped
