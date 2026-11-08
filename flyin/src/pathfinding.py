"""Find the cheapest path of a single drone (Dijkstra).

This module only answers: "what is the best route for ONE drone if it were
alone on the map?". It ignores zone and link capacities, so it does not
schedule a whole fleet. That is the job of a later step.
"""

import heapq
from dataclasses import dataclass

from flyin.src.map_data import MapData

ENTRY_COST: dict[str, int] = {
    "normal": 1,
    "priority": 1,
    "restricted": 2,
}


@dataclass(frozen=True)
class Path:
    """A route from one zone to another.

    Attributes:
        zones: Names of the zones visited, start and end included.
        turns: Total number of turns needed to follow the route.
        priority_zones: Number of priority zones entered on the route.
    """

    zones: tuple[str, ...]
    turns: int
    priority_zones: int


class Graph:
    """The zone network, stored as an adjacency dictionary.

    Each zone name maps to the sorted list of its neighbours. Connections
    are bidirectional, so each one is stored in both directions.
    """

    def __init__(self, map_data: MapData) -> None:
        """Build the graph from a parsed map."""
        self._zone_types: dict[str, str] = {
            name: zone.zone_type for name, zone in map_data.zones.items()
        }
        self._neighbors: dict[str, list[str]] = {
            name: [] for name in map_data.zones
        }
        for connection in map_data.connections:
            self._neighbors[connection.zone1].append(connection.zone2)
            self._neighbors[connection.zone2].append(connection.zone1)
        for names in self._neighbors.values():
            names.sort()

    def has_zone(self, name: str) -> bool:
        """Tell whether a zone exists."""
        return name in self._zone_types

    def zone_type(self, name: str) -> str:
        """Return the type of a zone (normal, priority, ...)."""
        return self._zone_types[name]

    def neighbors(self, name: str) -> list[str]:
        """Return the zones directly connected to `name`, sorted."""
        return self._neighbors[name]

    def entry_cost(self, name: str) -> int | None:
        """Return the turns needed to enter a zone, None if it is blocked."""
        return ENTRY_COST.get(self._zone_types[name])


class PathFinder:
    """Dijkstra search on a Graph.

    The cost of a path is a pair (turns, non_priority_zones), compared in
    this order: fewer turns always wins, and among paths with the same
    number of turns, the one crossing the most priority zones wins.
    """

    def __init__(self, graph: Graph) -> None:
        """Store the graph to search in."""
        self._graph = graph

    def find_path(self, start: str, end: str) -> Path | None:
        """Return the cheapest path from start to end, or None.

        None means no valid path exists: the start or the end is blocked,
        or every route is cut by blocked zones or missing connections.

        Raises:
            ValueError: If start or end is not a zone of the graph.
        """
        for name in (start, end):
            if not self._graph.has_zone(name):
                raise ValueError(f"unknown zone '{name}'")
        if (self._graph.entry_cost(start) is None
                or self._graph.entry_cost(end) is None):
            return None

        best: dict[str, tuple[int, int]] = {start: (0, 0)}
        previous: dict[str, str] = {}
        queue: list[tuple[int, int, str]] = [(0, 0, start)]

        while queue:
            turns, others, name = heapq.heappop(queue)
            if (turns, others) > best[name]:
                continue  # outdated queue entry, a better one was seen
            if name == end:
                return self._build_path(previous, start, end, turns)
            for neighbor in self._graph.neighbors(name):
                cost = self._graph.entry_cost(neighbor)
                if cost is None:
                    continue  # blocked zone
                is_priority = self._graph.zone_type(neighbor) == "priority"
                candidate = (turns + cost, others + (0 if is_priority else 1))
                if neighbor not in best or candidate < best[neighbor]:
                    best[neighbor] = candidate
                    previous[neighbor] = name
                    heapq.heappush(queue, (*candidate, neighbor))
        return None

    def _build_path(self, previous: dict[str, str], start: str, end: str,
                    turns: int) -> Path:
        """Walk back from end to start through `previous`."""
        zones = [end]
        while zones[-1] != start:
            zones.append(previous[zones[-1]])
        zones.reverse()
        priority = sum(
            1 for name in zones[1:]
            if self._graph.zone_type(name) == "priority"
        )
        return Path(tuple(zones), turns, priority)


def find_best_path(map_data: MapData) -> Path | None:
    """Find the cheapest path from the start hub to the end hub.

    Raises:
        ValueError: If the map has no start hub or no end hub.
    """
    if map_data.start_hub is None or map_data.end_hub is None:
        raise ValueError("map has no start_hub or end_hub")
    finder = PathFinder(Graph(map_data))
    return finder.find_path(map_data.start_hub, map_data.end_hub)
