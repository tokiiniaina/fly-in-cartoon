"""Space-time A* planner (greedy, one drone after the other)."""

import heapq
import itertools
from abc import ABC, abstractmethod

from flyin.src.engine.distances import DistanceMap
from flyin.src.engine.errors import NoPathError
from flyin.src.engine.model import Plan, Position, Trajectory
from flyin.src.engine.network import Network
from flyin.src.engine.reservations import ReservationTable
from flyin.src.engine.rules import TRANSIT_HOLDS_LINK_BOTH_TURNS


class Scheduler(ABC):
    """A strategy that turns a network into a plan."""

    @abstractmethod
    def plan(self, network: Network) -> Plan:
        """Return one trajectory per drone."""


class _Node:
    """A search node, linked to its parent to rebuild the path."""

    __slots__ = ("position", "parent")

    def __init__(self, position: Position,
                 parent: "_Node | None") -> None:
        """Store the position and the previous node."""
        self.position = position
        self.parent = parent


class SpaceTimeScheduler(Scheduler):
    """Plans each drone with A* in (position, turn) space.

    Each planned trajectory is committed in a reservation table, so a
    later drone can never invalidate an earlier one. The horizon
    guarantees termination and rules out deadlocks.
    """

    def plan(self, network: Network) -> Plan:
        """Plan the drones one after the other."""
        dist = DistanceMap(network)
        base = dist.to_end(network.start)
        if base is None:
            raise NoPathError("the end zone is unreachable from start")
        table = ReservationTable(network)
        plan = Plan()
        makespan = 0
        for drone in range(1, network.nb_drones + 1):
            traj = self._search(network, dist, table, makespan + base)
            table.commit(traj)
            plan.trajectories[drone] = traj
            makespan = max(makespan, traj.arrival_turn())
        return plan

    @staticmethod
    def _heuristic(dist: DistanceMap, position: Position) -> int | None:
        """Lower bound of the turns left from a position."""
        if position.zone is not None:
            return dist.to_end(position.zone)
        assert position.transit is not None
        rest = dist.to_end(position.transit[1])
        return None if rest is None else rest + 1

    def _search(self, net: Network, dist: DistanceMap,
                table: ReservationTable, horizon: int) -> Trajectory:
        """A* for one drone. Cost: (arrival, finite waits, non-priority)."""
        tie = itertools.count()
        first = _Node(Position(zone=net.start), None)
        base = dist.to_end(net.start) or 0
        heap: list[tuple[int, int, int, int, int, _Node]] = [
            (base, 0, 0, next(tie), 0, first)]
        seen: set[tuple[Position, int]] = set()

        def push(turn: int, waits: int, nonprio: int,
                 position: Position, parent: _Node) -> None:
            rest = self._heuristic(dist, position)
            if rest is None:
                return
            heapq.heappush(heap, (turn + rest, waits, nonprio,
                                  next(tie), turn,
                                  _Node(position, parent)))

        while heap:
            _, waits, nonprio, _, turn, node = heapq.heappop(heap)
            pos = node.position
            if (pos, turn) in seen:
                continue
            seen.add((pos, turn))
            if pos.zone == net.end:
                return self._build(net, node)
            if turn >= horizon:
                continue
            if pos.transit is not None:      # forced landing, no wait
                dest = pos.transit[1]
                push(turn + 1, waits,
                     nonprio + (0 if net.is_priority(dest) else 1),
                     Position(zone=dest), node)
                continue
            assert pos.zone is not None
            here = pos.zone
            if table.zone_free(here, turn + 1):
                finite = net.zone_capacity(here) is not None
                push(turn + 1, waits + (1 if finite else 0), nonprio,
                     Position(zone=here), node)
            for dest in net.neighbors(here):
                if not table.link_free(here, dest, turn + 1):
                    continue
                if net.is_restricted(dest):
                    if TRANSIT_HOLDS_LINK_BOTH_TURNS and \
                            not table.link_free(here, dest, turn + 2):
                        continue
                    if not table.zone_free(dest, turn + 2):
                        continue
                    push(turn + 1, waits, nonprio,
                         Position(transit=(here, dest)), node)
                elif table.zone_free(dest, turn + 1):
                    push(turn + 1, waits,
                         nonprio + (0 if net.is_priority(dest) else 1),
                         Position(zone=dest), node)
        raise NoPathError("no route found within the horizon")

    @staticmethod
    def _build(net: Network, last: _Node) -> Trajectory:
        """Rebuild the trajectory from the goal node."""
        positions: list[Position] = []
        node: _Node | None = last
        while node is not None:
            positions.append(node.position)
            node = node.parent
        positions.reverse()
        return Trajectory(net.end, positions)
