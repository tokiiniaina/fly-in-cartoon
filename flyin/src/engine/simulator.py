"""Turn-by-turn simulation: every drone moves closer to the end."""

from collections import Counter

from flyin.src.engine.distances import ENTRY_COST, DistanceMap
from flyin.src.map_data import MapData

MAX_TURNS = 10000


class Drone:
    """One drone: its zone, and its flight if it is in transit."""

    def __init__(self, drone_id: int, zone: str) -> None:
        """Create a drone waiting in `zone`."""
        self.drone_id = drone_id
        self.zone = zone
        self.flying_from: str | None = None
        self.flying_to: str | None = None


class Simulator:
    """Plays the simulation and returns one text line per turn."""

    def __init__(self, data: MapData) -> None:
        """Prepare drones, distances and lookup tables."""
        assert data.start_hub is not None and data.end_hub is not None
        self._data = data
        self._start: str = data.start_hub
        self._end: str = data.end_hub
        self._dist = DistanceMap(data)
        self._drones = [Drone(i, self._start)
                        for i in range(1, data.nb_drones + 1)]
        self._neighbors: dict[str, list[str]] = {n: [] for n in data.zones}
        self._link_cap: dict[frozenset[str], int] = {}
        self._link_name: dict[frozenset[str], str] = {}
        for c in data.connections:
            key = frozenset((c.zone1, c.zone2))
            self._link_cap[key] = c.max_link_capacity
            self._link_name[key] = f"{c.zone1}-{c.zone2}"
            self._neighbors[c.zone1].append(c.zone2)
            self._neighbors[c.zone2].append(c.zone1)
        self._inside: Counter[str] = Counter()

    def _is_limited(self, zone: str) -> bool:
        """Start and end have no capacity limit."""
        return zone not in (self._start, self._end)

    def _delivered(self, drone: Drone) -> bool:
        """Whether the drone reached the end zone."""
        return drone.zone == self._end and drone.flying_to is None

    def _can_enter(self, zone: str) -> bool:
        """Whether the zone still has room."""
        if not self._is_limited(zone):
            return True
        return self._inside[zone] < self._data.zones[zone].max_drones

    def run(self) -> list[str]:
        """Simulate until every drone is delivered."""
        if self._dist.to_end(self._start) is None:
            raise ValueError("the end zone cannot be reached")
        lines: list[str] = []
        while not all(self._delivered(d) for d in self._drones):
            if len(lines) >= MAX_TURNS:
                raise ValueError("simulation does not finish")
            lines.append(" ".join(self._play_turn()))
        return lines

    def _play_turn(self) -> list[str]:
        """Play one turn and return the movements as text."""
        moves: list[str] = []
        links: Counter[frozenset[str]] = Counter()
        landed: set[int] = set()
        for drone in self._drones:
            if drone.flying_to is not None and drone.flying_from:
                key = frozenset((drone.flying_from, drone.flying_to))
                links[key] += 1
                drone.zone = drone.flying_to
                drone.flying_from = drone.flying_to = None
                if self._is_limited(drone.zone):
                    self._inside[drone.zone] += 1
                landed.add(drone.drone_id)
                moves.append(f"D{drone.drone_id}-{drone.zone}")
        waiting = [d for d in self._drones if not self._delivered(d)
                   and d.zone != self._end and d.flying_to is None
                   and d.drone_id not in landed]
        waiting.sort(key=lambda d: (self._dist.to_end(d.zone) or 0,
                                    d.drone_id))
        for drone in waiting:
            target = self._choose(drone, links)
            if target is not None:
                moves.append(self._move(drone, target, links))
        return moves

    def _choose(self, drone: Drone,
                links: Counter[frozenset[str]]) -> str | None:
        """Best neighbor that is closer to the end and has room."""
        here = self._dist.to_end(drone.zone)
        best: tuple[int, int, int, str] | None = None
        for nxt in self._neighbors[drone.zone]:
            dist = self._dist.to_end(nxt)
            kind = self._data.zones[nxt].zone_type
            if dist is None or here is None or dist >= here:
                continue
            key = frozenset((drone.zone, nxt))
            if links[key] >= self._link_cap[key]:
                continue
            if not self._can_enter(nxt):
                continue
            capacity = self._link_cap[key]
            if self._is_limited(nxt):
                capacity = min(
                    capacity, self._data.zones[nxt].max_drones
                )
            score = (ENTRY_COST[kind] + dist,
                     0 if kind == "priority" else 1, -capacity, nxt)
            if best is None or score < best:
                best = score
        return None if best is None else best[3]

    def _move(self, drone: Drone, target: str,
              links: Counter[frozenset[str]]) -> str:
        """Apply a move and return its text."""
        key = frozenset((drone.zone, target))
        links[key] += 1
        if self._is_limited(drone.zone):
            self._inside[drone.zone] -= 1
        if self._data.zones[target].zone_type == "restricted":
            drone.flying_from, drone.flying_to = drone.zone, target
            return f"D{drone.drone_id}-{self._link_name[key]}"
        if self._is_limited(target):
            self._inside[target] += 1
        drone.zone = target

        return f"D{drone.drone_id}-{target}"
