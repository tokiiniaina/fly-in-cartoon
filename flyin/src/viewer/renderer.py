"""Animated frames: static base + drones + HUD, and GIF export."""

from __future__ import annotations

import math
from collections import defaultdict

from PIL import Image, ImageDraw, ImageFilter

from flyin.src.viewer.art import THEMES, Layout, build_base
from flyin.src.viewer.draw import (FLIP_X, LANCZOS, OUT, ROOT, Painter, Pt,
                                   font, lerp_pt, smooth)
from flyin.src.viewer.model import Spot, ViewScene, replay


# --------------------------------------------------------------------------
# Drone sprite
# --------------------------------------------------------------------------
def fallback_drone(h: int) -> Image.Image:
    """Procedural drone used when assets/drone.png is missing."""
    p = Painter(h, h)
    c = h / 2
    p.ellipse(c, c * .85, h * .3, h * .27, (236, 236, 242), OUT, 2.5)
    p.ellipse(c + h * .1, c * .85, h * .13, h * .13, (20, 24, 34),
              (70, 200, 240), 3)
    p.line([(c - h * .05, c * .85 - h * .26), (c - h * .05, h * .05)],
           (200, 200, 210), 3)
    p.ellipse(c, c * 1.35, h * .12, h * .05, (90, 200, 240))
    return p.done()


def load_drone(height: int) -> Image.Image:
    """Load the drone sprite scaled to the wanted height."""
    path = ROOT / "assets" / "drone.png"
    try:
        img = Image.open(path).convert("RGBA")
    except OSError:
        img = fallback_drone(256)
    w = max(1, round(img.width * height / img.height))
    return img.resize((w, height), LANCZOS)


def shadow_sprite(width: int) -> Image.Image:
    """Soft elliptical ground shadow."""
    h = max(6, width // 3)
    img = Image.new("RGBA", (width + 24, h + 24), (0, 0, 0, 0))
    ImageDraw.Draw(img).ellipse([12, 12, 12 + width, 12 + h],
                                fill=(60, 50, 90, 110))
    return img.filter(ImageFilter.GaussianBlur(5))


# --------------------------------------------------------------------------
# Frame renderer
# --------------------------------------------------------------------------
CROWD_LIMITS = (2, 4, 9, 10 ** 9)   # drones sharing one zone ...
CROWD_SCALES = (1.0, 0.82, 0.68, 0.55)  # ... and the sprite size they get


class Renderer:
    """Builds animated frames: static base + drones + HUD."""

    def __init__(self, scene: ViewScene, turns: list[dict[int, str]],
                 lines: list[str], w: int = 1280, h: int = 720,
                 title: str = "FLY-IN", target: int = 0,
                 margins: tuple[int, int, int] = (56, 70, 50),
                 dx: float = 0.0) -> None:
        """Prepare the base image and the sprites for a scene."""
        self.sc, self.w, self.h, self.lines = scene, w, h, lines
        self.title, self.target = title, target
        self.lay = Layout(scene, w, h, margins=margins, shift=dx)
        self.base = build_base(scene, self.lay, w, h)
        self.states = replay(scene, turns)
        self.T = len(turns)
        sh = int(max(48, min(170, self.lay.hw * 0.80)))
        self.sprite = load_drone(sh)
        # crowded zones use smaller drones: (normal, mirrored, shadow)
        self.sizes: list[tuple[Image.Image, Image.Image, Image.Image]] = []
        for k in CROWD_SCALES:
            spr = self.sprite.resize((max(8, int(self.sprite.width * k)),
                                      max(8, int(self.sprite.height * k))),
                                     LANCZOS)
            self.sizes.append((spr, spr.transpose(FLIP_X),
                               shadow_sprite(int(spr.width * .75))))
        self.slots: list[dict[int, Pt]] = []
        self.sidx: list[dict[int, int]] = []
        for st in self.states:
            offs, idx = self._slots(st)
            self.slots.append(offs)
            self.sidx.append(idx)
        self.face = self._facing()

    # -- positions --------------------------------------------------------
    def ground(self, s: Spot) -> Pt:
        """Ground point (platform centre or middle of a connection)."""
        a = self.lay.center(self.sc.zones[s.zone])
        if not s.dest:
            return a
        return lerp_pt(a, self.lay.center(self.sc.zones[s.dest]), .5)

    def _slots(self, state: dict[int, Spot]
               ) -> tuple[dict[int, Pt], dict[int, int]]:
        """Offsets and size index of each drone, spread when sharing."""
        groups: dict[Spot, list[int]] = defaultdict(list)
        for d in sorted(state):
            groups[state[d]].append(d)
        out: dict[int, Pt] = {}
        size: dict[int, int] = {}
        for ids in groups.values():
            n = len(ids)
            si = next(j for j, lim in enumerate(CROWD_LIMITS) if n <= lim)
            # spread drones on a sunflower pattern that fits the platform
            step = min(self.sprite.width * CROWD_SCALES[si] * 0.62,
                       self.lay.hw * 0.85 / math.sqrt(n))
            for k, d in enumerate(ids):
                size[d] = si
                if n == 1:
                    out[d] = (0.0, 0.0)
                    continue
                ang, rad = k * 2.4 + .6, step * math.sqrt(k + .5)
                out[d] = (math.cos(ang) * rad, math.sin(ang) * rad * .55)
        return out, size

    def _facing(self) -> list[dict[int, bool]]:
        """For each state, whether each drone looks left."""
        cur = {d: False for d in self.states[0]}
        res = [dict(cur)]
        for i in range(self.T):
            for d in cur:
                a = self.ground(self.states[i][d])[0]
                b = self.ground(self.states[i + 1][d])[0]
                if b < a - 1:
                    cur[d] = True
                elif b > a + 1:
                    cur[d] = False
            res.append(dict(cur))
        return res

    # -- drawing ----------------------------------------------------------
    def frame(self, tau: float, clock: float = 0.0,
              hud: bool = True) -> Image.Image:
        """Render the image for animation time ``tau`` (in turns)."""
        img = self.base.copy()
        tau = max(0.0, min(float(self.T), tau))
        i = min(int(tau), self.T - 1) if self.T else 0
        frac = (tau - i) if self.T else 0.0
        e = smooth(frac)
        sa = self.states[i]
        sb = self.states[min(i + 1, self.T)]
        near = min(i + (1 if frac > .5 else 0), self.T)
        drawn: list[tuple[float, Image.Image, Image.Image, float, float,
                          float]] = []
        for d in sa:
            ga, gb = self.ground(sa[d]), self.ground(sb[d])
            oa, ob = self.slots[i][d], self.slots[min(i + 1, self.T)][d]
            gx = ga[0] + (gb[0] - ga[0]) * e + oa[0] + (ob[0] - oa[0]) * e
            gy = ga[1] + (gb[1] - ga[1]) * e + oa[1] + (ob[1] - oa[1]) * e
            normal, mirrored, shadow = self.sizes[self.sidx[near][d]]
            lift = math.sin(math.pi * e) * normal.height * .3 \
                if sa[d] != sb[d] else 0.0
            bob = math.sin(clock * 3.2 + d * 1.3) * 3
            hover = normal.height * .62 + lift + bob
            spr = mirrored if self.face[near][d] else normal
            drawn.append((gy, spr, shadow, gx, hover, lift))
        for gy, spr, shadow, gx, hover, lift in drawn:
            k = max(.55, 1 - lift / 260)
            sh = shadow if k > .98 else shadow.resize(
                (int(shadow.width * k), int(shadow.height * k)))
            img.paste(sh, (int(gx - sh.width / 2),
                           int(gy - sh.height / 2 + 4)), sh)
        for gy, spr, _, gx, hover, _ in sorted(drawn, key=lambda t: t[0]):
            img.paste(spr, (int(gx - spr.width / 2),
                            int(gy - hover - spr.height / 2)), spr)
        if hud:
            self.hud(img, tau)
        return img

    def hud(self, img: Image.Image, tau: float) -> None:
        """Draw the counters, the legend and the moves of the turn."""
        d = ImageDraw.Draw(img, "RGBA")
        shown = min(self.T, math.ceil(tau - 1e-9))
        done_state = self.states[min(self.T, int(tau + 1e-6))]
        delivered = sum(1 for s in done_state.values()
                        if s.zone == self.sc.end and not s.dest)
        d.rounded_rectangle([24, 20, 350, 130], 18,
                            fill=(255, 255, 255, 225),
                            outline=(200, 202, 216), width=2)
        title = self.title if len(self.title) <= 22 else \
            self.title[:21] + "."
        d.text((44, 30), title, font=font(22), fill=(52, 50, 66))
        d.text((44, 62), f"Turn {shown} / {self.T}", font=font(20),
               fill=(70, 120, 220))
        if self.target:
            d.text((330, 64), f"Target {self.target}", font=font(16),
                   fill=(130, 130, 148), anchor="ra")
        d.text((44, 90), f"Delivered {delivered}/{self.sc.drones}",
               font=font(16), fill=(60, 160, 80))
        d.rounded_rectangle([44, 114, 330, 122], 4, fill=(226, 228, 238))
        if self.T:
            wbar = 286 * tau / self.T
            if wbar >= 8:
                d.rounded_rectangle([44, 114, 44 + wbar, 122], 4,
                                    fill=(90, 170, 240))
        y0 = self.h - 70
        d.rounded_rectangle([24, y0, 560, y0 + 40], 14,
                            fill=(255, 255, 255, 215),
                            outline=(200, 202, 216), width=2)
        x = 40
        for name in ("normal", "priority", "restricted", "blocked"):
            d.rounded_rectangle([x, y0 + 12, x + 16, y0 + 28], 5,
                                fill=THEMES[name]["top"], outline=OUT)
            d.text((x + 22, y0 + 20), name, font=font(14),
                   fill=(80, 78, 96), anchor="lm")
            x += 22 + int(font(14).getlength(name)) + 24
        if shown >= 1 and self.lines:
            line = f"T{shown}: " + self.lines[min(shown, len(self.lines)) - 1]
            if len(line) > 80:
                line = line[:77] + "..."
            wd = font(15).getlength(line) + 30
            d.rounded_rectangle([self.w - 24 - wd, self.h - 70,
                                 self.w - 24, self.h - 30], 14,
                                fill=(52, 50, 66, 225))
            d.text((self.w - 24 - wd / 2, self.h - 50), line,
                   font=font(15), fill=(240, 240, 250), anchor="mm")


def export_gif(rend: Renderer, path: str, speed: float,
               scale: float = 0.6, fps: int = 16) -> None:
    """Write an animated GIF of the whole simulation."""
    n = max(1, int(rend.T / speed * fps))
    taus = [0.0] * (fps // 2) + [rend.T * i / n for i in range(n + 1)]
    taus += [float(rend.T)] * (fps * 2)
    frames = []
    for i, tau in enumerate(taus):
        img = rend.frame(tau, i / fps)
        size = (int(img.width * scale), int(img.height * scale))
        frames.append(img.resize(size, LANCZOS).quantize(
            colors=128, method=Image.Quantize.MEDIANCUT,
            dither=Image.Dither.NONE))
    frames[0].save(path, save_all=True, append_images=frames[1:],
                   duration=1000 // fps, loop=0, optimize=False)
