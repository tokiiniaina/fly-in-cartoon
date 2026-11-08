"""What the viewer needs: a light scene and the replay of the turns."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from flyin.src.map_data import MapData


@dataclass
class ViewZone:
    """A zone as drawn on screen."""

    name: str
    x: int
    y: int
    kind: str = "normal"
    color: str = ""
    cap: int = 1
    role: str = "hub"


@dataclass
class ViewScene:
    """The map as the viewer sees it."""

    drones: int
    zones: dict[str, ViewZone] = field(default_factory=dict)
    links: list[tuple[str, str, int]] = field(default_factory=list)
    start: str = ""
    end: str = ""


def scene_from_map(data: MapData) -> ViewScene:
    """Convert the parsed map into a scene the viewer can draw."""
    if data.start_hub is None or data.end_hub is None:
        raise ValueError("the map needs a start_hub and an end_hub")
    scene = ViewScene(data.nb_drones, start=data.start_hub,
                      end=data.end_hub)
    for name, zone in data.zones.items():
        role = ("start" if name == data.start_hub else
                "end" if name == data.end_hub else "hub")
        color = "" if zone.color == "none" else zone.color
        scene.zones[name] = ViewZone(name, zone.x, zone.y, zone.zone_type,
                                     color, zone.max_drones, role)
    for conn in data.connections:
        scene.links.append((conn.zone1, conn.zone2, conn.max_link_capacity))
    return scene


MOVE_RE = re.compile(r"^D(\d+)-(\S+)$")


def parse_moves(lines: list[str]) -> list[dict[int, str]]:
    """Turn the simulator's text lines into {drone: destination} dicts."""
    turns: list[dict[int, str]] = []
    for line in lines:
        turn: dict[int, str] = {}
        for tok in line.split():
            found = MOVE_RE.match(tok)
            if found:
                turn[int(found.group(1))] = found.group(2)
        turns.append(turn)
    return turns


@dataclass(frozen=True)
class Spot:
    """Where a drone is: in a zone, or in flight towards ``dest``."""

    zone: str
    dest: str = ""


def replay(scene: ViewScene, turns: list[dict[int, str]]
           ) -> list[dict[int, Spot]]:
    """Replay the moves; states[t][drone] is the position after turn t."""
    cur = {d: Spot(scene.start) for d in range(1, scene.drones + 1)}
    states = [dict(cur)]
    for turn in turns:
        for drone, target in turn.items():
            if drone not in cur:
                continue
            if target in scene.zones:
                cur[drone] = Spot(target)
                continue
            a, _, b = target.partition("-")
            origin = cur[drone].zone
            cur[drone] = Spot(origin, b if origin == a else a)
        states.append(dict(cur))
    return states
