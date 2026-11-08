"""Distance of every zone to the end zone using reverse Dijkstra."""

import heapq
from typing import Protocol

from flyin.src.map_data import MapData


ENTRY_COST: dict[str, int] = {
    "normal": 1,
    "priority": 1,
    "restricted": 2,
}


class DistanceNetwork(Protocol):
    """Minimal network interface needed by DistanceMap."""

    end: str

    def neighbors(self, zone: str) -> list[str]:
        """Return zones connected to the given zone."""
        ...

    def entry_cost(self, zone: str) -> int | None:
        """Return the cost of entering a zone."""
        ...


class DistanceMap:
    """Store the shortest distance from every zone to the end."""

    def __init__(self, data: MapData | DistanceNetwork) -> None:
        """Build the reverse Dijkstra distance table."""
        self._dist: dict[str, int] = {}
        if isinstance(data, MapData):
            self._build_from_map(data)
        else:
            self._build_from_network(data)

    def _build_from_map(self, data: MapData) -> None:
        """Build distances from the parser's map model."""
        if data.end_hub is None:
            self._dist = {}
            return

        neighbors: dict[str, list[str]] = {
            name: [] for name in data.zones
        }
        for connection in data.connections:
            neighbors[connection.zone1].append(connection.zone2)
            neighbors[connection.zone2].append(connection.zone1)

        end = data.end_hub
        if data.zones[end].zone_type not in ENTRY_COST:
            self._dist = {}
            return

        distances: dict[str, int] = {end: 0}
        queue: list[tuple[int, str]] = [(0, end)]

        while queue:
            distance, zone = heapq.heappop(queue)
            if distance > distances[zone]:
                continue

            cost = ENTRY_COST[data.zones[zone].zone_type]
            for previous in neighbors[zone]:
                if data.zones[previous].zone_type not in ENTRY_COST:
                    continue

                candidate = distance + cost
                if candidate < distances.get(previous, candidate + 1):
                    distances[previous] = candidate
                    heapq.heappush(queue, (candidate, previous))

        self._dist = distances

    def _build_from_network(self, network: DistanceNetwork) -> None:
        """Build distances from the engine network interface."""
        end = network.end
        if network.entry_cost(end) is None:
            self._dist = {}
            return

        distances: dict[str, int] = {end: 0}
        queue: list[tuple[int, str]] = [(0, end)]

        while queue:
            distance, zone = heapq.heappop(queue)
            if distance > distances[zone]:
                continue

            cost = network.entry_cost(zone)
            if cost is None:
                continue

            for previous in network.neighbors(zone):
                if network.entry_cost(previous) is None:
                    continue

                candidate = distance + cost
                if candidate < distances.get(previous, candidate + 1):
                    distances[previous] = candidate
                    heapq.heappush(queue, (candidate, previous))

        self._dist = distances

    def to_end(self, zone: str) -> int | None:
        """Return the distance to the end, or None if unreachable."""
        return self._dist.get(zone)
