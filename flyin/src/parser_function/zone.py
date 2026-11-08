"""Parse zone declarations."""

import re

from flyin.src.zone import Zone


def parse_zone(line: str, line_number: int) -> tuple[str, Zone]:
    """Parse a zone declaration and return its kind and data."""

    if ":" not in line:
        raise ValueError(
            f"Line {line_number}: invalid zone declaration"
        )

    prefix, content = line.split(":", 1)
    prefix = prefix.strip()
    content = content.strip()

    if prefix not in ("hub", "start_hub", "end_hub"):
        raise ValueError(
            f"Line {line_number}: unknown zone declaration '{prefix}'"
        )

    parts = content.split()

    if len(parts) < 3:
        raise ValueError(
            f"Line {line_number}: expected a name and two coordinates"
        )

    name = parts[0]

    if "-" in name:
        raise ValueError(
            f"Line {line_number}: zone names cannot contain dashes"
        )

    try:
        x = int(parts[1])
        y = int(parts[2])
    except ValueError:
        raise ValueError(
            f"Line {line_number}: coordinates must be integers"
        ) from None

    zone_type = "normal"
    color = "none"
    max_drones = 1

    metadata_text = " ".join(parts[3:])

    if metadata_text:
        if not (
            metadata_text.startswith("[")
            and metadata_text.endswith("]")
        ):
            raise ValueError(
                f"Line {line_number}: invalid metadata block"
            )

        metadata_text = metadata_text[1:-1].strip()

        if not metadata_text:
            raise ValueError(
                f"Line {line_number}: metadata block cannot be empty"
            )

        metadata: dict[str, str] = {}

        for item in metadata_text.split():
            if not re.fullmatch(r"[a-z_]+=[^\s=\[\]]+", item):
                raise ValueError(
                    f"Line {line_number}: invalid metadata item '{item}'"
                )

            key, value = item.split("=", 1)

            if key not in ("zone", "color", "max_drones"):
                raise ValueError(
                    f"Line {line_number}: unknown zone metadata '{key}'"
                )

            if key in metadata:
                raise ValueError(
                    f"Line {line_number}: duplicate metadata '{key}'"
                )

            metadata[key] = value

        zone_type = metadata.get("zone", "normal")
        color = metadata.get("color", "none")

        if zone_type not in (
            "normal", "blocked", "restricted", "priority"
        ):
            raise ValueError(
                f"Line {line_number}: invalid zone type '{zone_type}'"
            )

        if prefix == "hub" and "max_drones" in metadata:
            value = metadata["max_drones"]

            if not value.isascii() or not value.isdigit():
                raise ValueError(
                    f"Line {line_number}: max_drones must "
                    "be a positive integer"
                )

            max_drones = int(value)

            if max_drones <= 0:
                raise ValueError(
                    f"Line {line_number}: max_drones must be positive"
                )

    zone = Zone(
        name=name,
        x=x,
        y=y,
        zone_type=zone_type,
        color=color,
        max_drones=max_drones,
    )

    return prefix, zone
