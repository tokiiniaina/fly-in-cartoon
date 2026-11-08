"""Positions, movements, trajectories and plans."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Position:
    """A drone is in a zone, or in transit towards a restricted zone."""

    zone: str | None = None
    transit: tuple[str, str] | None = None   # (origin, destination)


@dataclass(frozen=True)
class Movement:
    """One drone movement during one turn."""

    drone_id: int
    src: str
    dst: str
    in_transit: bool
    link_label: str


@dataclass
class Trajectory:
    """positions[k] is the state at the end of turn k (0 = start)."""

    end_zone: str
    positions: list[Position] = field(default_factory=list)

    def arrival_turn(self) -> int:
        """First turn at which the drone is in the end zone."""
        for turn, position in enumerate(self.positions):
            if position.zone == self.end_zone:
                return turn
        raise ValueError("trajectory never reaches the end zone")

    def position_at(self, turn: int) -> Position:
        """State at a turn (stays in the end zone once delivered)."""
        return self.positions[min(turn, len(self.positions) - 1)]


@dataclass
class Plan:
    """All trajectories, indexed by drone id."""

    trajectories: dict[int, Trajectory] = field(default_factory=dict)

    def makespan(self) -> int:
        """Turn at which the last drone arrives."""
        return max(
            (t.arrival_turn() for t in self.trajectories.values()),
            default=0,
        )
