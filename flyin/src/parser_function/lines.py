"""Read useful lines from a map file."""

from pathlib import Path


def read_lines(file_path: str) -> list[tuple[int, str]]:
    """Read non-empty, comment-free lines with their original line numbers.

    Args:
        file_path: Path to the map file to read.

    Returns:
        A list of ``(line_number, line)`` pairs.
    """
    lines: list[tuple[int, str]] = []

    with Path(file_path).open("r", encoding="utf-8") as file:
        for line_number, raw in enumerate(file, start=1):
            line = raw.split("#", 1)[0].strip()

            if not line:
                continue

            lines.append((line_number, line))
    return lines
