"""Parse complete map files."""

from flyin.src.map_data import MapData
from flyin.src.parser_function.connection import parse_connection
from flyin.src.parser_function.lines import read_lines
from flyin.src.parser_function.nb_drones import parse_nb_drones
from flyin.src.parser_function.zone import parse_zone


class MapParser:
    """Parse a map file into a MapData object."""

    def parse(self, file_path: str) -> MapData:
        """Parse the drone count, zones and connections in a map file."""
        return _parse_map(file_path)


def parse_map(file_path: str) -> MapData:
    """Keep the original functional parser API for compatibility."""
    return MapParser().parse(file_path)


def _parse_map(file_path: str) -> MapData:
    """Parse the drone count and zones from a map file."""
    lines = read_lines(file_path)
    if not lines:
        raise ValueError("Empty map file")
    first_line_number, first_line = lines[0]

    if not first_line.startswith("nb_drones:"):
        if not any(line.startswith("nb_drones") for _, line in lines):
            raise ValueError("Missing 'nb_drones' declaration")
        raise ValueError(
            f"Line {first_line_number}: "
            "'nb_drones' must be the first declaration"
        )

    map_data = MapData()
    nb_drones_found = False

    seen_connections: set[tuple[str, str]] = set()
    for line_number, line in lines:
        if line.startswith("nb_drones"):
            if nb_drones_found:
                raise ValueError(
                    f"Line {line_number}: duplicate nb_drones declaration"
                )

            map_data.nb_drones = parse_nb_drones(line, line_number)
            nb_drones_found = True

        elif line.startswith(("hub:", "start_hub:", "end_hub:")):
            kind, zone = parse_zone(line, line_number)

            if zone.name in map_data.zones:
                raise ValueError(
                    f"Line {line_number}: duplicate zone name '{zone.name}'"
                )

            map_data.zones[zone.name] = zone

            if kind == "start_hub":
                if map_data.start_hub is not None:
                    raise ValueError(
                        f"Line {line_number}: duplicate start_hub declaration"
                    )
                map_data.start_hub = zone.name

            elif kind == "end_hub":
                if map_data.end_hub is not None:
                    raise ValueError(
                        f"Line {line_number}: duplicate end_hub declaration"
                    )
                map_data.end_hub = zone.name

        elif line.startswith("connection:"):
            connection = parse_connection(line, line_number)
            if connection.zone1 not in map_data.zones:
                raise ValueError(
                    f"Line {line_number}: unknown zone "
                    f"'{connection.zone1}'"
                )
            if connection.zone2 not in map_data.zones:
                raise ValueError(
                    f"Line {line_number}: unknown zone "
                    f"'{connection.zone2}'"
                )
            first, second = sorted((connection.zone1, connection.zone2))
            connection_key = (first, second)

            if connection_key in seen_connections:
                raise ValueError(
                    f"Line {line_number}: duplicate connection "
                    f"'{connection.zone1}-{connection.zone2}'"
                )
            seen_connections.add(connection_key)
            map_data.connections.append(connection)

        else:
            raise ValueError(
                f"Line {line_number}: unknown declaration '{line}'"
            )

    if not nb_drones_found:
        raise ValueError("Missing 'nb_drones' declaration")

    if map_data.start_hub is None:
        raise ValueError("Missing 'start_hub' declaration")

    if map_data.end_hub is None:
        raise ValueError("Missing 'end_hub' declaration")

    return map_data
