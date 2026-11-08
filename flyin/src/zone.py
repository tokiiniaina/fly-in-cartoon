"""Define the Zone data model."""

from dataclasses import dataclass


@dataclass
class Zone:
    """A zone of the map."""

    name: str
    x: int
    y: int
    zone_type: str = "normal"
    color: str = "none"
    max_drones: int = 1
