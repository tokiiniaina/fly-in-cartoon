"""Independent rule checker that replays a plan turn by turn."""

from collections import defaultdict
from dataclasses import dataclass, field

from flyin.src.engine.errors import SimulationError
from flyin.src.engine.model import Movement, Plan, Position
from flyin.src.engine.network import Network
from flyin.src.engine.rules import TRANSIT_HOLDS_LINK_BOTH_TURNS, link_slot


@dataclass
class TurnRecord:
    """Everything that happened during one turn."""

    turn: int
    movements: list[Movement] = field(default_factory=list)
    delivered: int = 0


class Simulation:
    """Recomputes its own counters. Never uses the reservation table."""

    def __init__(self, network: Network, plan: Plan) -> None:
        """Keep the network and the plan."""
        self._net = network
        self._plan = plan

    def run(self) -> list[TurnRecord]:
        """Replay the plan. Raise SimulationError on any violation."""
        net = self._net
        self._check_starts()
        records: list[TurnRecord] = []
        for turn in range(1, self._plan.makespan() + 1):
            record = TurnRecord(turn)
            zones: dict[str, int] = defaultdict(int)
            links: dict[tuple[str, str], int] = defaultdict(int)
            for drone, traj in sorted(self._plan.trajectories.items()):
                prev = traj.position_at(turn - 1)
                cur = traj.position_at(turn)
                if prev.zone == net.end:
                    continue
                move = self._movement(turn, drone, prev, cur)
                if move is not None:
                    record.movements.append(move)
                    self._count_link(links, prev, cur, move)
                if cur.zone is not None:
                    if cur.zone == net.end:
                        record.delivered += 1
                    elif net.zone_capacity(cur.zone) is not None:
                        zones[cur.zone] += 1
            self._check_capacities(turn, zones, links)
            record.delivered += self._already_delivered(turn)
            records.append(record)
        self._check_all_delivered(len(records))
        return records

    def _check_starts(self) -> None:
        for drone, traj in self._plan.trajectories.items():
            if traj.positions[0] != Position(zone=self._net.start):
                raise SimulationError(0, f"D{drone} does not start "
                                         "in the start zone")
            if traj.positions[-1].zone != self._net.end:
                raise SimulationError(0, f"D{drone} is not delivered")

    def _already_delivered(self, turn: int) -> int:
        """Drones that arrived before `turn` (they are not tracked)."""
        return sum(
            1 for t in self._plan.trajectories.values()
            if t.position_at(turn - 1).zone == self._net.end)

    def _movement(self, turn: int, drone: int, prev: Position,
                  cur: Position) -> Movement | None:
        """Derive and validate what one drone did during one turn."""
        net = self._net
        if prev.transit is not None:                    # landing
            src, dest = prev.transit
            if cur.zone != dest:
                raise SimulationError(
                    turn, f"D{drone} must land on '{dest}' after the "
                          "flight and cannot wait on the link")
            return Movement(drone, src, dest, False,
                            net.link_label(src, dest))
        assert prev.zone is not None
        if cur.zone == prev.zone:
            return None                                 # waits
        if cur.zone is not None:                        # normal move
            self._check_step(turn, drone, prev.zone, cur.zone)
            if net.is_restricted(cur.zone):
                raise SimulationError(
                    turn, f"D{drone} enters restricted '{cur.zone}' "
                          "in one turn")
            return Movement(drone, prev.zone, cur.zone, False,
                            net.link_label(prev.zone, cur.zone))
        assert cur.transit is not None                  # take-off
        src, dest = cur.transit
        if src != prev.zone:
            raise SimulationError(turn, f"D{drone} takes off from "
                                        f"'{src}' but is in '{prev.zone}'")
        self._check_step(turn, drone, src, dest)
        if not net.is_restricted(dest):
            raise SimulationError(
                turn, f"D{drone} uses transit towards '{dest}', "
                      "which is not restricted")
        return Movement(drone, src, dest, True, net.link_label(src, dest))

    def _check_step(self, turn: int, drone: int, src: str,
                    dest: str) -> None:
        if self._net.entry_cost(dest) is None:
            raise SimulationError(
                turn, f"D{drone} enters blocked zone '{dest}'")
        if dest not in self._net.neighbors(src):
            raise SimulationError(
                turn, f"D{drone}: '{src}' and '{dest}' are not connected")

    @staticmethod
    def _count_link(links: dict[tuple[str, str], int], prev: Position,
                    cur: Position, move: Movement) -> None:
        """Count a link use (a landing counts only under rule A1)."""
        landing = prev.transit is not None
        if landing and not TRANSIT_HOLDS_LINK_BOTH_TURNS:
            return
        links[link_slot(move.src, move.dst)] += 1

    def _check_capacities(self, turn: int, zones: dict[str, int],
                          links: dict[tuple[str, str], int]) -> None:
        net = self._net
        for zone, count in zones.items():
            capacity = net.zone_capacity(zone)
            if capacity is not None and count > capacity:
                raise SimulationError(
                    turn, f"zone '{zone}' holds {count} drones "
                          f"(max {capacity})")
        for (a, b), count in links.items():
            if count > net.link_capacity(a, b):
                raise SimulationError(
                    turn, f"link '{net.link_label(a, b)}' carries "
                          f"{count} drones "
                          f"(max {net.link_capacity(a, b)})")

    def _check_all_delivered(self, turns: int) -> None:
        for drone, traj in self._plan.trajectories.items():
            if traj.position_at(turns).zone != self._net.end:
                raise SimulationError(
                    turns, f"D{drone} is not delivered at the end")
