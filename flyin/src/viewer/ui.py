"""Widgets of the menus, drawn with Pillow (cached sprites)."""

from __future__ import annotations

import math
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFilter

from flyin.src.viewer.draw import LANCZOS, RGB, SS, font, shade

INK: RGB = (52, 50, 66)
MUTED: RGB = (130, 130, 148)
LINE: RGB = (200, 202, 216)
BLUE: RGB = (90, 170, 240)
GREEN: RGB = (110, 200, 90)
RED: RGB = (240, 100, 110)
GOLD: RGB = (250, 200, 60)
PAD = 12
LEVEL_COLORS: dict[str, RGB] = {
    "easy": (118, 214, 80), "medium": (250, 190, 70),
    "hard": (240, 100, 110), "challenger": (178, 108, 232),
    "tests": (160, 160, 172),
}


def _shadow(size: tuple[int, int], box: list[float], radius: float,
            alpha: int = 70) -> Image.Image:
    """A blurred drop shadow for a rounded box (big-canvas pixels)."""
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).rounded_rectangle(
        box, radius, fill=(60, 60, 90, alpha))
    return layer.filter(ImageFilter.GaussianBlur(5 * SS))


def _icon(d: ImageDraw.ImageDraw, name: str, cx: float, cy: float,
          r: float) -> None:
    """Draw a white pictogram centred on (cx, cy)."""
    w = (255, 255, 255)
    if name == "play":
        d.polygon([(cx - r * .35, cy - r * .5), (cx - r * .35, cy + r * .5),
                   (cx + r * .55, cy)], fill=w)
    elif name == "pause":
        for k in (-1, 1):
            d.rounded_rectangle([cx + k * r * .32 - r * .16, cy - r * .5,
                                 cx + k * r * .32 + r * .16, cy + r * .5],
                                r * .08, fill=w)
    elif name in ("prev", "next"):
        s = -1 if name == "prev" else 1
        d.polygon([(cx - s * r * .45, cy - r * .5),
                   (cx - s * r * .45, cy + r * .5),
                   (cx + s * r * .25, cy)], fill=w)
        d.rectangle([cx + s * r * .3 - r * .08, cy - r * .5,
                     cx + s * r * .3 + r * .08, cy + r * .5], fill=w)
    elif name == "restart":
        d.arc([cx - r * .5, cy - r * .5, cx + r * .5, cy + r * .5],
              40, 330, fill=w, width=max(2, int(r * .18)))
        d.polygon([(cx + r * .62, cy - r * .55), (cx + r * .15, cy - r * .5),
                   (cx + r * .5, cy - r * .05)], fill=w)
    elif name == "home":
        d.polygon([(cx - r * .6, cy), (cx, cy - r * .55), (cx + r * .6, cy)],
                  fill=w)
        d.rectangle([cx - r * .4, cy, cx + r * .4, cy + r * .5], fill=w)
    elif name in ("plus", "minus"):
        t = r * .1
        d.rectangle([cx - r * .45, cy - t, cx + r * .45, cy + t], fill=w)
        if name == "plus":
            d.rectangle([cx - t, cy - r * .45, cx + t, cy + r * .45],
                        fill=w)
    elif name == "left":
        d.polygon([(cx + r * .3, cy - r * .5), (cx + r * .3, cy + r * .5),
                   (cx - r * .4, cy)], fill=w)
    elif name == "right":
        d.polygon([(cx - r * .3, cy - r * .5), (cx - r * .3, cy + r * .5),
                   (cx + r * .4, cy)], fill=w)


@lru_cache(maxsize=256)
def pill(w: int, h: int, fill: RGB, text: str = "", size: int = 22,
         hover: bool = False, icon: str = "") -> Image.Image:
    """A rounded button sprite (with a PAD margin for its shadow)."""
    big = (w + 2 * PAD) * SS, (h + 2 * PAD) * SS
    rad = min(w, h) / 2 * SS if icon else h * .42 * SS
    box = [PAD * SS, PAD * SS, (PAD + w) * SS, (PAD + h) * SS]
    lift = 2 * SS if hover else 0
    box = [box[0], box[1] - lift, box[2], box[3] - lift]
    img = _shadow(big, [box[0], box[1] + 4 * SS, box[2], box[3] + 4 * SS],
                  rad)
    d = ImageDraw.Draw(img)
    face = shade(fill, 1.1) if hover else fill
    d.rounded_rectangle(box, rad, fill=face, outline=shade(fill, .7),
                        width=3 * SS)
    d.rounded_rectangle([box[0] + 6 * SS, box[1] + 5 * SS,
                         box[2] - 6 * SS, box[1] + h * .42 * SS],
                        rad * .6, fill=shade(face, 1.18))
    cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
    if icon:
        _icon(d, icon, cx, cy, min(w, h) / 2 * SS * .8)
    if text:
        d.text((cx, cy + SS), text, font=font(size * SS),
               fill=(255, 255, 255), anchor="mm",
               stroke_width=SS, stroke_fill=shade(fill, .62))
    return img.resize((big[0] // SS, big[1] // SS), LANCZOS)


def blit(img: Image.Image, sprite: Image.Image, x: int, y: int) -> None:
    """Paste a sprite built with PAD so its box starts at (x, y)."""
    img.alpha_composite(sprite, (x - PAD, y - PAD))


def star_points(cx: float, cy: float, r: float) -> list[tuple[float, float]]:
    """The ten corners of a five-branch star."""
    pts = []
    for i in range(10):
        rad = r if i % 2 == 0 else r * .45
        a = -math.pi / 2 + i * math.pi / 5
        pts.append((cx + math.cos(a) * rad, cy + math.sin(a) * rad))
    return pts


@lru_cache(maxsize=64)
def stars_sprite(count: int, size: int, total: int = 3) -> Image.Image:
    """A row of stars, ``count`` of them filled."""
    gap = size * .25
    w = int(total * size + (total - 1) * gap) + 4
    big = Image.new("RGBA", (w * SS, (size + 4) * SS), (0, 0, 0, 0))
    d = ImageDraw.Draw(big)
    for i in range(total):
        cx = (2 + size / 2 + i * (size + gap)) * SS
        pts = star_points(cx, (size / 2 + 2) * SS, size / 2 * SS)
        on = i < count
        d.polygon(pts, fill=GOLD if on else (222, 224, 234),
                  outline=(214, 150, 30) if on else (190, 192, 206))
        d.line(pts + [pts[0]], fill=(214, 150, 30) if on
               else (190, 192, 206), width=2 * SS, joint="curve")
    return big.resize((w, size + 4), LANCZOS)


@lru_cache(maxsize=64)
def badge(text: str, color: RGB, size: int = 13) -> Image.Image:
    """A small coloured label."""
    f = font(size * SS)
    w = int(f.getlength(text) / SS) + 18
    h = size + 10
    big = Image.new("RGBA", (w * SS, h * SS), (0, 0, 0, 0))
    d = ImageDraw.Draw(big)
    d.rounded_rectangle([0, 0, w * SS - 1, h * SS - 1], h * SS / 2,
                        fill=color, outline=shade(color, .7), width=2 * SS)
    d.text((w * SS / 2, h * SS / 2 + SS), text, font=f,
           fill=(255, 255, 255), anchor="mm", stroke_width=SS // 2,
           stroke_fill=shade(color, .6))
    return big.resize((w, h), LANCZOS)


def panel(w: int, h: int, alpha: int = 235, radius: int = 26
          ) -> Image.Image:
    """A white rounded panel with a soft shadow (PAD margin)."""
    big = (w + 2 * PAD) * SS, (h + 2 * PAD) * SS
    box = [PAD * SS, PAD * SS, (PAD + w) * SS, (PAD + h) * SS]
    img = _shadow(big, [box[0], box[1] + 5 * SS, box[2], box[3] + 5 * SS],
                  radius * SS, 60)
    ImageDraw.Draw(img).rounded_rectangle(
        box, radius * SS, fill=(255, 255, 255, alpha), outline=LINE,
        width=2 * SS)
    return img.resize((big[0] // SS, big[1] // SS), LANCZOS)


def card(w: int, h: int, thumb: Image.Image | None, title: str,
         level: str, drones: int, best: int, stars: int,
         hover: bool, error: str = "") -> Image.Image:
    """A map card for the selection screen (PAD margin)."""
    base = panel(w, h, 255, 22)
    img = Image.new("RGBA", base.size, (0, 0, 0, 0))
    img.alpha_composite(base)
    th = int(h * .62)
    area = Image.new("RGBA", (w - 16, th), (236, 241, 252, 255))
    top = Image.linear_gradient("L").resize(area.size)
    area = Image.composite(
        Image.new("RGBA", area.size, (226, 232, 250, 255)),
        Image.new("RGBA", area.size, (250, 246, 252, 255)), top)
    if thumb is not None:
        tx = (area.width - thumb.width) // 2
        ty = (area.height - thumb.height) // 2
        area.alpha_composite(thumb, (tx, ty))
    mask = Image.new("L", area.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [0, 0, area.width - 1, area.height - 1], 16, fill=255)
    img.paste(area, (PAD + 8, PAD + 8), mask)
    d = ImageDraw.Draw(img)
    d.text((PAD + 16, PAD + th + 22), title, font=font(19), fill=INK,
           anchor="lm")
    tag = badge(level.upper(), LEVEL_COLORS.get(level, (160, 160, 172)))
    img.alpha_composite(tag, (PAD + 16, PAD + h - 34))
    if drones:
        d.text((PAD + 26 + tag.width, PAD + h - 22), f"{drones} drones",
               font=font(13), fill=MUTED, anchor="lm")
    if error:
        veil = Image.new("RGBA", (w - 16, th), (240, 100, 110, 150))
        img.paste(veil, (PAD + 8, PAD + 8), mask)
        d.text((PAD + w / 2, PAD + th / 2 + 8), "INVALID MAP",
               font=font(20), fill=(255, 255, 255), anchor="mm")
    elif stars:
        sp = stars_sprite(stars, 18)
        img.alpha_composite(sp, (PAD + w - 16 - sp.width, PAD + h - 34))
    if best and not error:
        d.text((PAD + w - 20, PAD + th + 22), f"best {best}",
               font=font(13), fill=MUTED, anchor="rm")
    if hover:
        ImageDraw.Draw(img).rounded_rectangle(
            [PAD, PAD, PAD + w, PAD + h], 22, outline=BLUE, width=4)
    return img
