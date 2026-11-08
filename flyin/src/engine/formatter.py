"""Output format of the subject: one line per turn."""

from flyin.src.engine.simulation import TurnRecord


class OutputFormatter:
    """Turns records into lines such as 'D1-roof1 D2-hub-roof1'."""

    def line(self, record: TurnRecord) -> str:
        """One turn as text."""
        return " ".join(
            f"D{m.drone_id}-{m.link_label if m.in_transit else m.dst}"
            for m in record.movements
        )

    def lines(self, records: list[TurnRecord]) -> list[str]:
        """All turns as text."""
        return [self.line(r) for r in records]
