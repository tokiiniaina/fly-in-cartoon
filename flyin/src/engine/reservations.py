"""Counters of planned zone and link usage over time."""

from collections import defaultdict

from flyin.src.engine.model import Trajectory
from flyin.src.engine.network import Network
from flyin.src.engine.rules import TRANSIT_HOLDS_LINK_BOTH_TURNS, link_slot


class ReservationTable:
    """Single source of truth for what the planner already reserved."""

    def __init__(self, network: Network) -> None:
        """Start with an empty table."""
        self._net = network
        self._zone: dict[tuple[str, int], int] = defaultdict(int)
        self._link: dict[tuple[tuple[str, str], int], int] = \
            defaultdict(int)

    def zone_free(self, zone: str, turn: int) -> bool:
        """Room in `zone` at the end of `turn`."""
        capacity = self._net.zone_capacity(zone)
        return capacity is None or self._zone[(zone, turn)] < capacity

    def link_free(self, a: str, b: str, turn: int) -> bool:
        """Room on the link a-b during `turn`."""
        used = self._link[(link_slot(a, b), turn)]
        return used < self._net.link_capacity(a, b)

    def commit(self, traj: Trajectory) -> None:
        """Reserve every occupation of a trajectory."""
        self._apply(traj, 1)

    def release(self, traj: Trajectory) -> None:
        """Exact inverse of commit."""
        self._apply(traj, -1)

    def _apply(self, traj: Trajectory, sign: int) -> None:
        """Add `sign` to every zone and link used by the trajectory."""
        pos = traj.positions
        for turn in range(1, len(pos)):
            prev, cur = pos[turn - 1], pos[turn]
            if cur.zone is not None \
                    and self._net.zone_capacity(cur.zone) is not None:
                self._zone[(cur.zone, turn)] += sign
            if prev.zone is not None and cur.zone is not None \
                    and prev.zone != cur.zone:
                ends = (prev.zone, cur.zone)
            elif prev.zone is not None and cur.transit is not None:
                ends = cur.transit
            elif prev.transit is not None and cur.zone is not None \
                    and TRANSIT_HOLDS_LINK_BOTH_TURNS:
                ends = prev.transit
            else:
                continue
            self._link[(link_slot(*ends), turn)] += sign
