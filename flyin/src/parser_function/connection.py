"""Parse connection declarations."""

import re

from flyin.src.connection import Connection


def parse_connection(
    line: str,
    line_number: int,
) -> Connection:
    """Parse a connection declaration and return its data."""
    line = line.strip()

    match = re.fullmatch(
        r"connection:\s*([^\s\-\[\]]+)-([^\s\-\[\]]+)(?:\s+(.*))?",
        line,
    )

    if match is None:
        raise ValueError(
            f"Line {line_number}: invalid connection declaration"
        )

    zone1, zone2, metadata_block = match.groups()

    if zone1 == zone2:
        raise ValueError(
            f"Line {line_number}: a connection must link two "
            "different zones"
        )

    max_link_capacity = 1

    if metadata_block is not None:
        if not (
            metadata_block.startswith("[")
            and metadata_block.endswith("]")
        ):
            raise ValueError(
                f"Line {line_number}: invalid metadata block"
            )

        metadata_text = metadata_block[1:-1].strip()

        metadata_match = re.fullmatch(
            r"max_link_capacity\s*=\s*([^\s=\[\]]+)",
            metadata_text,
        )

        if metadata_match is None:
            raise ValueError(
                f"Line {line_number}: invalid connection metadata"
            )

        value = metadata_match.group(1)

        if not value.isascii() or not value.isdigit():
            raise ValueError(
                f"Line {line_number}: max_link_capacity must be "
                "a positive integer"
            )

        max_link_capacity = int(value)

        if max_link_capacity <= 0:
            raise ValueError(
                f"Line {line_number}: max_link_capacity must be "
                "positive"
            )

    return Connection(
        zone1=zone1,
        zone2=zone2,
        max_link_capacity=max_link_capacity,
    )
