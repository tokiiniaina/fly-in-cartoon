"""Interpretation choices left open by the subject (see README)."""

# A1: a flight to a restricted zone holds its link during both turns.
TRANSIT_HOLDS_LINK_BOTH_TURNS = True

# A2: link capacity is shared by the two directions.
LINK_SHARED_BY_DIRECTION = True


def link_slot(a: str, b: str) -> tuple[str, str]:
    """Identity of a link for capacity counting, for a move a -> b."""
    if LINK_SHARED_BY_DIRECTION:
        return (a, b) if a <= b else (b, a)
    return (a, b)
