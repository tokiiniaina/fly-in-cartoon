"""Read-only view of a parsed map, used by the planner."""

from flyin.src.engine.errors import NoPathError
from flyin.src.map_data import MapData

ENTRY_COST: dict[str, int] = {"normal": 1, "priority": 1, "restricted": 2}


class Network:
    """Zones, links, entry costs and capacities."""

    def __init__(self, data: MapData) -> None:
        """Index the map. Blocked zones never appear as neighbors."""
        if data.start_hub is None or data.end_hub is None:
            raise ValueError("map has no start_hub or end_hub")
        self.start: str = data.start_hub
        self.end: str = data.end_hub
        self.nb_drones: int = data.nb_drones
        self._data = data
        self._adjacent: dict[str, list[str]] = {n: [] for n in data.zones}
        self._links: dict[tuple[str, str], tuple[int, str]] = {}
        for conn in data.connections:
            key = self._key(conn.zone1, conn.zone2)
            self._links[key] = (conn.max_link_capacity,
                                f"{conn.zone1}-{conn.zone2}")
            for src, dst in ((conn.zone1, conn.zone2),
                             (conn.zone2, conn.zone1)):
                if self.entry_cost(dst) is not None:
                    self._adjacent[src].append(dst)
        for names in self._adjacent.values():
            names.sort()

    @staticmethod
    def _key(a: str, b: str) -> tuple[str, str]:
        return (a, b) if a <= b else (b, a)

    def neighbors(self, zone: str) -> list[str]:
        """Enterable zones directly connected to `zone`, sorted."""
        return self._adjacent[zone]

    def entry_cost(self, zone: str) -> int | None:
        """Turns needed to enter a zone, None if it is blocked."""
        return ENTRY_COST.get(self._data.zones[zone].zone_type)

    def is_restricted(self, zone: str) -> bool:
        """Whether entering the zone takes two turns."""
        return self._data.zones[zone].zone_type == "restricted"

    def is_priority(self, zone: str) -> bool:
        """Whether the zone is a preferred one."""
        return self._data.zones[zone].zone_type == "priority"

    def zone_capacity(self, zone: str) -> int | None:
        """Capacity of a zone, None (unlimited) for start and end."""
        if zone in (self.start, self.end):
            return None
        return self._data.zones[zone].max_drones

    def zone_color(self, zone: str) -> str:
        """Color word of a zone ('none' when unset)."""
        return self._data.zones[zone].color

    def link_capacity(self, a: str, b: str) -> int:
        """Capacity of the link between a and b."""
        return self._links[self._key(a, b)][0]

    def link_label(self, a: str, b: str) -> str:
        """Link name written in the order of the map file."""
        return self._links[self._key(a, b)][1]

    def validate(self) -> None:
        """Raise NoPathError if the start or the end is blocked."""
        if self.entry_cost(self.start) is None:
            raise NoPathError("the start zone is blocked")
        if self.entry_cost(self.end) is None:
            raise NoPathError("the end zone is blocked")
