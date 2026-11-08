"""Validate a simulator output independently from the simulator."""

from collections import Counter
from dataclasses import dataclass

from flyin.src.map_data import MapData


@dataclass
class DroneState:
    """Store the current state of one drone."""

    zone: str | None
    flying_from: str | None = None
    flying_to: str | None = None


class OutputChecker:
    """Replay output lines and check every map constraint."""

    def __init__(self, data: MapData) -> None:
        """Prepare the map indexes and the initial drone states."""
        if data.start_hub is None or data.end_hub is None:
            raise ValueError("the map needs a start_hub and an end_hub")

        self._data = data
        self._start = data.start_hub
        self._end = data.end_hub
        self._states = {
            drone_id: DroneState(zone=self._start)
            for drone_id in range(1, data.nb_drones + 1)
        }
        self._neighbors: dict[str, set[str]] = {
            name: set() for name in data.zones
        }
        self._link_capacities: dict[frozenset[str], int] = {}

        for connection in data.connections:
            key = frozenset((connection.zone1, connection.zone2))
            self._neighbors[connection.zone1].add(connection.zone2)
            self._neighbors[connection.zone2].add(connection.zone1)
            self._link_capacities[key] = connection.max_link_capacity

    def check(self, lines: list[str]) -> None:
        """Replay all lines and raise ValueError for an invalid output."""
        for turn, line in enumerate(lines, start=1):
            self._check_turn(turn, line)

        self._check_delivery(len(lines))

    def _check_turn(self, turn: int, line: str) -> None:
        """Validate one turn and update all drone states."""
        moves = self._parse_line(turn, line)
        zone_occupancy = self._current_occupancy()
        link_usage: Counter[frozenset[str]] = Counter()
        departures: Counter[str] = Counter()
        arrivals: Counter[str] = Counter()
        next_states = {
            drone_id: DroneState(
                zone=state.zone,
                flying_from=state.flying_from,
                flying_to=state.flying_to,
            )
            for drone_id, state in self._states.items()
        }

        for drone_id, destination in moves.items():
            state = self._states[drone_id]

            if state.zone == self._end:
                raise ValueError(
                    f"turn {turn}: D{drone_id} moves after delivery"
                )

            if state.flying_to is not None:
                self._check_landing(
                    turn,
                    drone_id,
                    state,
                    destination,
                    next_states[drone_id],
                    link_usage,
                    arrivals,
                )
                continue

            if state.zone is None:
                raise ValueError(
                    f"turn {turn}: D{drone_id} has no valid position"
                )

            self._check_departure(
                turn,
                drone_id,
                state,
                destination,
                next_states[drone_id],
                link_usage,
                departures,
                arrivals,
            )

        self._check_waiting_drones(turn, moves, next_states)
        self._check_zone_capacities(
            turn,
            zone_occupancy,
            departures,
            arrivals,
        )
        self._check_link_capacities(turn, link_usage)
        self._states = next_states

    def _parse_line(self, turn: int, line: str) -> dict[int, str]:
        """Parse one output line into drone ids and destination tokens."""
        moves: dict[int, str] = {}

        for token in line.split():
            if not token.startswith("D") or "-" not in token:
                raise ValueError(
                    f"turn {turn}: invalid movement '{token}'"
                )

            drone_text, destination = token[1:].split("-", 1)

            if not drone_text.isdigit() or not destination:
                raise ValueError(
                    f"turn {turn}: invalid movement '{token}'"
                )

            drone_id = int(drone_text)

            if drone_id not in self._states:
                raise ValueError(
                    f"turn {turn}: unknown drone D{drone_id}"
                )
            if drone_id in moves:
                raise ValueError(
                    f"turn {turn}: D{drone_id} moves twice"
                )

            moves[drone_id] = destination

        return moves

    def _check_landing(
        self,
        turn: int,
        drone_id: int,
        state: DroneState,
        destination: str,
        next_state: DroneState,
        link_usage: Counter[frozenset[str]],
        arrivals: Counter[str],
    ) -> None:
        """Validate the mandatory second turn of a restricted flight."""
        if destination != state.flying_to:
            raise ValueError(
                f"turn {turn}: D{drone_id} must land in "
                f"'{state.flying_to}'"
            )

        assert state.flying_from is not None
        assert state.flying_to is not None
        key = frozenset((state.flying_from, state.flying_to))
        link_usage[key] += 1
        arrivals[state.flying_to] += 1

        next_state.zone = state.flying_to
        next_state.flying_from = None
        next_state.flying_to = None

    def _check_departure(
        self,
        turn: int,
        drone_id: int,
        state: DroneState,
        destination: str,
        next_state: DroneState,
        link_usage: Counter[frozenset[str]],
        departures: Counter[str],
        arrivals: Counter[str],
    ) -> None:
        """Validate an ordinary move or a restricted-zone takeoff."""
        assert state.zone is not None

        if "-" in destination:
            parts = destination.split("-")
            if len(parts) != 2:
                raise ValueError(
                    f"turn {turn}: invalid restricted move "
                    f"'D{drone_id}-{destination}'"
                )
            source, target = parts
            if source != state.zone:
                raise ValueError(
                    f"turn {turn}: D{drone_id} is not in '{source}'"
                )
        else:
            source = state.zone
            target = destination

        self._check_connection(turn, drone_id, source, target)
        key = frozenset((source, target))
        link_usage[key] += 1
        departures[source] += 1

        target_zone = self._data.zones[target]
        if target_zone.zone_type == "restricted":
            if destination != f"{source}-{target}":
                raise ValueError(
                    f"turn {turn}: restricted move must include "
                    f"'{source}-{target}'"
                )
            next_state.zone = None
            next_state.flying_from = source
            next_state.flying_to = target
            return

        if "-" in destination:
            raise ValueError(
                f"turn {turn}: only restricted zones use a flight token"
            )

        arrivals[target] += 1
        next_state.zone = target

    def _check_connection(
        self,
        turn: int,
        drone_id: int,
        source: str,
        target: str,
    ) -> None:
        """Check that a movement uses a valid, enterable zone."""
        if source not in self._data.zones:
            raise ValueError(
                f"turn {turn}: D{drone_id} leaves unknown zone '{source}'"
            )
        if target not in self._data.zones:
            raise ValueError(
                f"turn {turn}: D{drone_id} enters unknown zone '{target}'"
            )
        if target not in self._neighbors[source]:
            raise ValueError(
                f"turn {turn}: '{source}' and '{target}' are not connected"
            )
        if self._data.zones[target].zone_type == "blocked":
            raise ValueError(
                f"turn {turn}: D{drone_id} enters blocked zone '{target}'"
            )

    def _check_waiting_drones(
        self,
        turn: int,
        moves: dict[int, str],
        next_states: dict[int, DroneState],
    ) -> None:
        """Keep waiting drones in zones and reject transit waiting."""
        for drone_id, state in self._states.items():
            if drone_id in moves:
                continue
            if state.flying_to is not None:
                raise ValueError(
                    f"turn {turn}: D{drone_id} must land in "
                    f"'{state.flying_to}'"
                )
            if state.zone is None:
                raise ValueError(
                    f"turn {turn}: D{drone_id} is waiting in transit"
                )
            next_states[drone_id].zone = state.zone

    def _current_occupancy(self) -> Counter[str]:
        """Count drones currently inside limited zones."""
        occupancy: Counter[str] = Counter()
        for state in self._states.values():
            if state.zone is None or state.zone in (self._start, self._end):
                continue
            occupancy[state.zone] += 1
        return occupancy

    def _check_zone_capacities(
        self,
        turn: int,
        occupancy: Counter[str],
        departures: Counter[str],
        arrivals: Counter[str],
    ) -> None:
        """Check zone capacity after departures and arrivals."""
        for name, zone in self._data.zones.items():
            if name in (self._start, self._end):
                continue

            final_count = (
                occupancy[name] - departures[name] + arrivals[name]
            )
            if final_count > zone.max_drones:
                raise ValueError(
                    f"turn {turn}: zone '{name}' contains "
                    f"{final_count} drones, maximum is {zone.max_drones}"
                )

    def _check_link_capacities(
        self,
        turn: int,
        link_usage: Counter[frozenset[str]],
    ) -> None:
        """Check shared link capacities for both movement directions."""
        for link, count in link_usage.items():
            capacity = self._link_capacities[link]
            if count > capacity:
                endpoints = "-".join(sorted(link))
                raise ValueError(
                    f"turn {turn}: link '{endpoints}' carries "
                    f"{count} drones, maximum is {capacity}"
                )

    def _check_delivery(self, turns: int) -> None:
        """Ensure that every drone reached the end zone."""
        for drone_id, state in self._states.items():
            if state.zone != self._end:
                raise ValueError(
                    f"after turn {turns}: D{drone_id} was not delivered"

                )
