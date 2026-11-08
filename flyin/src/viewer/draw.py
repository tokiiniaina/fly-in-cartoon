"""Drawing helpers: colours, geometry, fonts and a supersampling painter."""

from __future__ import annotations

import colorsys
import hashlib
import math
import re
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[3]
Pt = tuple[float, float]
RGB = tuple[int, int, int]
OUT: RGB = (46, 42, 56)
SS = 2  # supersampling factor for the static scene
LANCZOS = Image.Resampling.LANCZOS
FLIP_X = Image.Transpose.FLIP_LEFT_RIGHT


NAMED: dict[str, RGB] = {
    "red": (240, 96, 108), "green": (118, 214, 80),
    "blue": (86, 150, 240), "yellow": (250, 214, 70),
    "purple": (178, 108, 232), "orange": (250, 150, 60),
    "gray": (160, 160, 172), "grey": (160, 160, 172),
    "cyan": (80, 210, 230), "pink": (246, 140, 190),
    "brown": (170, 116, 72), "black": (70, 70, 84),
    "white": (240, 240, 246), "lime": (190, 235, 70),
    "teal": (60, 180, 170), "magenta": (230, 80, 200),
    "maroon": (170, 60, 80), "gold": (245, 190, 50),
    "violet": (150, 110, 235), "indigo": (100, 90, 200),
    "navy": (60, 90, 170), "crimson": (220, 60, 90),
    "silver": (200, 204, 214), "turquoise": (70, 220, 200),
}
NEUTRAL: RGB = (214, 220, 234)


def zone_color(name: str) -> RGB:
    """Map any colour word to an RGB triple (hash fallback)."""
    key = name.strip().lower()
    if key in NAMED:
        return NAMED[key]
    if re.fullmatch(r"#?[0-9a-f]{6}", key):
        key = key.lstrip("#")
        return int(key[0:2], 16), int(key[2:4], 16), int(key[4:6], 16)
    hue = int(hashlib.md5(key.encode()).hexdigest()[:6], 16) % 360
    r, g, b = colorsys.hsv_to_rgb(hue / 360, 0.55, 0.95)
    return int(r * 255), int(g * 255), int(b * 255)


def shade(c: RGB, f: float) -> RGB:
    """Darken (f < 1) or lighten (f > 1) a colour."""
    if f <= 1:
        return (int(c[0] * f), int(c[1] * f), int(c[2] * f))
    t = f - 1
    return tuple(int(v + (255 - v) * t) for v in c)  # type: ignore


def lerp_pt(a: Pt, b: Pt, t: float) -> Pt:
    """Linear interpolation between two points."""
    return a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t


def smooth(t: float) -> float:
    """Smoothstep easing."""
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def rounded(pts: list[Pt], r: float, n: int = 5) -> list[Pt]:
    """Round the corners of a polygon with quadratic curves."""
    out: list[Pt] = []
    m = len(pts)
    for i in range(m):
        p0, p1, p2 = pts[i - 1], pts[i], pts[(i + 1) % m]
        l1, l2 = math.dist(p0, p1), math.dist(p1, p2)
        a = lerp_pt(p1, p0, min(r, l1 / 2) / l1)
        b = lerp_pt(p1, p2, min(r, l2 / 2) / l2)
        for k in range(n + 1):
            t = k / n
            out.append((
                (1 - t) ** 2 * a[0] + 2 * (1 - t) * t * p1[0] + t * t * b[0],
                (1 - t) ** 2 * a[1] + 2 * (1 - t) * t * p1[1] + t * t * b[1],
            ))
    return out


_FONTS: dict[int, ImageFont.FreeTypeFont | ImageFont.ImageFont] = {}
FONT_FILES = ("DejaVuSans-Bold.ttf", "arialbd.ttf", "Arial Bold.ttf",
              "Helvetica.ttc", "LiberationSans-Bold.ttf")


def font(px: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Return a bold font of the given pixel size (cached)."""
    px = max(6, int(px))
    if px not in _FONTS:
        for name in FONT_FILES:
            try:
                _FONTS[px] = ImageFont.truetype(name, px)
                break
            except OSError:
                continue
        else:
            _FONTS[px] = ImageFont.load_default(size=px)
    return _FONTS[px]


class Painter:
    """Tiny supersampling wrapper around ImageDraw (coordinates in px)."""

    def __init__(self, w: int, h: int, ss: int = SS) -> None:
        self.w, self.h, self.ss = w, h, ss
        self.k = 1.0  # line width scale (small for thumbnails)
        self.img = Image.new("RGBA", (w * ss, h * ss), (0, 0, 0, 0))
        self.d = ImageDraw.Draw(self.img)

    def _s(self, pts: list[Pt]) -> list[Pt]:
        return [(x * self.ss, y * self.ss) for x, y in pts]

    def poly(self, pts: list[Pt], fill: Optional[RGB | tuple[int, ...]],
             outline: Optional[RGB] = None, width: float = 0) -> None:
        """Filled polygon with an optional round-joined outline."""
        p = self._s(pts)
        if fill is not None:
            self.d.polygon(p, fill=fill)
        if outline and width:
            self.d.line(p + [p[0]], fill=outline,
                        width=max(1, int(width * self.ss * self.k)),
                        joint="curve")

    def line(self, pts: list[Pt], fill: RGB, width: float) -> None:
        """Polyline with round joints."""
        self.d.line(self._s(pts), fill=fill,
                    width=max(1, int(width * self.ss * self.k)),
                        joint="curve")

    def ellipse(self, x: float, y: float, rx: float, ry: float,
                fill: Optional[RGB | tuple[int, ...]],
                outline: Optional[RGB] = None, width: float = 0) -> None:
        """Ellipse centred on (x, y)."""
        s = self.ss
        self.d.ellipse([(x - rx) * s, (y - ry) * s,
                        (x + rx) * s, (y + ry) * s], fill=fill,
                       outline=outline if width else None,
                       width=max(1, int(width * s * self.k)))

    def pie(self, x: float, y: float, rx: float, ry: float,
            a0: int, a1: int, fill: RGB) -> None:
        """Pie slice (angles in degrees)."""
        s = self.ss
        self.d.pieslice([(x - rx) * s, (y - ry) * s,
                         (x + rx) * s, (y + ry) * s], a0, a1, fill=fill)

    def text(self, x: float, y: float, txt: str, size: int, fill: RGB
             ) -> None:
        """Centred text."""
        self.d.text((x * self.ss, y * self.ss), txt,
                    font=font(size * self.ss), fill=fill, anchor="mm")

    def measure(self, txt: str, size: int) -> float:
        """Width of a text in output pixels."""
        return float(font(size * self.ss).getlength(txt)) / self.ss

    def done(self) -> Image.Image:
        """Downsample to the final size."""
        return self.img.resize((self.w, self.h), LANCZOS)
