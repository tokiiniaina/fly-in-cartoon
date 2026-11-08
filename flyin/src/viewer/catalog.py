"""The list of playable maps, their level and the saved scores."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from flyin.src.viewer.draw import ROOT

LEVELS = ("easy", "medium", "hard", "challenger", "tests")
RECORDS = {"01_the_impossible_dream": 45}
SCORE_FILE = ROOT / ".flyin_scores.json"


@dataclass
class MapEntry:
    """One map file of the maps folder."""

    path: Path
    level: str
    title: str

    @property
    def key(self) -> str:
        """Stable identifier used in the score file."""
        return f"{self.level}/{self.path.stem}"

    @property
    def record(self) -> int:
        """Turns to beat for three stars (0 when unknown)."""
        return RECORDS.get(self.path.stem, 0)


def pretty(stem: str) -> str:
    """'02_simple_fork' -> 'Simple Fork'."""
    words = stem.split("_")
    if words and words[0].isdigit():
        words = words[1:]
    return " ".join(w.capitalize() for w in words)


def find_maps(root: Path | None = None) -> list[MapEntry]:
    """List every map found under the maps folder, level by level."""
    base = root or ROOT / "maps"
    out: list[MapEntry] = []
    for level in LEVELS:
        for path in sorted((base / level).glob("*.txt")):
            out.append(MapEntry(path, level, pretty(path.stem)))
    return out


def stars(turns: int, best: int, record: int) -> int:
    """Rate a result: 3 stars at the reference, fewer when it is slower."""
    ref = record or best
    if turns <= ref:
        return 3
    return 2 if turns <= ref * 1.25 else 1


def load_scores() -> dict[str, int]:
    """Read the best turn counts saved on disk."""
    try:
        raw = json.loads(SCORE_FILE.read_text())
    except (OSError, ValueError):
        return {}
    if not isinstance(raw, dict):
        return {}
    return {str(k): int(v) for k, v in raw.items()
            if isinstance(v, int)}


def save_score(key: str, turns: int) -> None:
    """Keep the best result of a map."""
    scores = load_scores()
    if key in scores and scores[key] <= turns:
        return
    scores[key] = turns
    try:
        SCORE_FILE.write_text(json.dumps(scores, indent=2))
    except OSError:
        pass
