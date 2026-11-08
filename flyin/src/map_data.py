"""Define the MapData data model."""

from dataclasses import dataclass, field

from flyin.src.connection import Connection
from flyin.src.zone import Zone


@dataclass
class MapData:
    """Store all parsed map information."""

    nb_drones: int = 0
    zones: dict[str, Zone] = field(default_factory=dict)
    connections: list[Connection] = field(default_factory=list)
    start_hub: str | None = None
    end_hub: str | None = None
