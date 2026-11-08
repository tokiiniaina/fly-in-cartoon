"""Static scene art: layout, platforms, bridges, decorations, background."""

from __future__ import annotations

import math
import random
from typing import Callable, Optional

from PIL import Image, ImageFilter

from flyin.src.viewer.draw import (NEUTRAL, OUT, Painter, Pt, RGB, lerp_pt,
                                   rounded, shade, zone_color)
from flyin.src.viewer.model import ViewScene, ViewZone


class Layout:
    """Computes the isometric projection that fits the whole map."""

    def __init__(self, scene: ViewScene, w: int, h: int,
                 margins: tuple[int, int, int] = (56, 70, 50),
                 max_hw: float = 150.0, shift: float = 0.0) -> None:
        """Fit the scene in w x h; margins are (top, bottom, side)."""
        zs = list(scene.zones.values())
        xs, ys = [z.x for z in zs], [z.y for z in zs]
        gaps = [max(abs(a.x - b.x), abs(a.y - b.y))
                for i, a in enumerate(zs) for b in zs[i + 1:]]
        gaps = [g for g in gaps if g > 0]
        ext = max(max(xs) - min(xs), max(ys) - min(ys), 1)
        self.s = min(0.64 * (min(gaps) if gaps else 2),
                     max(1.0, 0.34 * ext))
        sx: list[float] = []
        sy: list[float] = []
        for z in zs:
            for dx, dy in ((-.5, -.5), (.5, -.5), (.5, .5), (-.5, .5)):
                gx, gy = z.x + dx * self.s, z.y + dy * self.s
                sx.append(gx - gy)
                sy.append((gx + gy) / 2)
        top, bottom, side = margins
        bw = max(sx) - min(sx)
        bh = max(sy) - min(sy) + 1.7 * self.s
        avail = h - top - bottom
        self.u = min((w - 2 * side) / bw, avail / bh,
                     max_hw / self.s)
        self.ox = w / 2 + shift - (max(sx) + min(sx)) / 2 * self.u
        ymin = min(sy) - 0.9 * self.s
        self.oy = top + (avail - bh * self.u) / 2 - ymin * self.u
        self.hw = self.s * self.u      # half width of a platform
        self.T = 0.30 * self.hw        # slab thickness

    def to_screen(self, gx: float, gy: float) -> Pt:
        """Isometric projection of a grid position."""
        return (self.ox + (gx - gy) * self.u,
                self.oy + (gx + gy) * self.u / 2)

    def center(self, z: ViewZone) -> Pt:
        """Screen position of the middle of a platform's top."""
        return self.to_screen(z.x, z.y)


# --------------------------------------------------------------------------
# ViewScene art: platforms, paths, pads, trees, houses...
# --------------------------------------------------------------------------
THEMES: dict[str, dict[str, RGB]] = {
    "normal": dict(top=(150, 204, 72), patch=(126, 186, 62),
                   lip=(112, 172, 54), left=(146, 140, 156),
                   right=(174, 168, 182)),
    "priority": dict(top=(132, 222, 100), patch=(104, 202, 88),
                     lip=(88, 182, 74), left=(146, 140, 156),
                     right=(174, 168, 182)),
    "restricted": dict(top=(222, 128, 100), patch=(198, 102, 84),
                       lip=(176, 84, 68), left=(128, 106, 114),
                       right=(156, 130, 138)),
    "blocked": dict(top=(152, 158, 152), patch=(132, 138, 134),
                    lip=(112, 118, 114), left=(104, 104, 118),
                    right=(130, 130, 144)),
}
CREAM: RGB = (240, 236, 224)
CREAM_EDGE: RGB = (206, 200, 188)


class Art:
    """Draws the static part of the scene (everything but the drones)."""

    def __init__(self, scene: ViewScene, lay: Layout, w: int, h: int) -> None:
        self.sc, self.lay, self.w, self.h = scene, lay, w, h
        self.p = Painter(w, h)

    # -- helpers ----------------------------------------------------------
    def g(self, z: ViewZone, u: float, v: float) -> Pt:
        """Screen point of a local position (u, v in [-.5, .5])."""
        return self.lay.to_screen(z.x + u * self.lay.s,
                                  z.y + v * self.lay.s)

    def neighbours(self, z: ViewZone) -> list[Pt]:
        """Unit grid directions towards the connected zones."""
        out: list[Pt] = []
        for a, b, _ in self.sc.links:
            if z.name not in (a, b):
                continue
            o = self.sc.zones[b if a == z.name else a]
            d = math.hypot(o.x - z.x, o.y - z.y)
            if d:
                out.append(((o.x - z.x) / d, (o.y - z.y) / d))
        return out

    # -- paths ------------------------------------------------------------
    def strip(self, a: Pt, b: Pt, width: float, shift: float = 0,
              fill: RGB = CREAM, edge: RGB = CREAM_EDGE) -> None:
        """Cobbled strip between two grid points."""
        length = math.dist(a, b)
        if length < 1e-6:
            return
        ex, ey = (b[0] - a[0]) / length, (b[1] - a[1]) / length
        px, py = -ey * width / 2, ex * width / 2
        n = max(1, round(length / width))
        for i in range(n):
            t0, t1 = i / n, (i + 1) / n
            c0 = (a[0] + (b[0] - a[0]) * t0, a[1] + (b[1] - a[1]) * t0)
            c1 = (a[0] + (b[0] - a[0]) * t1, a[1] + (b[1] - a[1]) * t1)
            quad = [self.lay.to_screen(c0[0] + px, c0[1] + py),
                    self.lay.to_screen(c1[0] + px, c1[1] + py),
                    self.lay.to_screen(c1[0] - px, c1[1] - py),
                    self.lay.to_screen(c0[0] - px, c0[1] - py)]
            quad = [(x, y + shift) for x, y in quad]
            f = fill if i % 2 == 0 else shade(fill, 0.97)
            self.p.poly(rounded(quad, self.lay.hw * 0.03, 2), f, edge, 1.4)

    def ribbons(self) -> None:
        """Bridges between platforms (drawn below the platforms)."""
        zs = self.sc.zones
        links = sorted(self.sc.links, key=lambda k: (
            zs[k[0]].x + zs[k[0]].y + zs[k[1]].x + zs[k[1]].y))
        wd = 0.30 * self.lay.s
        for a, b, cap in links:
            za, zb = zs[a], zs[b]
            stone = (150, 144, 160)
            self.strip((za.x, za.y), (zb.x, zb.y), wd,
                       shift=self.lay.T * 0.35, fill=stone,
                       edge=OUT)
            self.strip((za.x, za.y), (zb.x, zb.y), wd)

    def top_paths(self, z: ViewZone) -> None:
        """Path from the platform centre to each edge."""
        s, wd = self.lay.s, 0.30 * self.lay.s
        for ex, ey in self.neighbours(z):
            t = (s / 2) / max(abs(ex), abs(ey))
            while t > wd:  # keep both corners of the end cap on the slab
                px, py = -ey * wd / 2, ex * wd / 2
                inside = all(max(abs(t * ex + sg * px),
                                 abs(t * ey + sg * py)) <= s / 2 * .97
                             for sg in (1, -1))
                if inside:
                    break
                t *= 0.96
            self.strip((z.x, z.y), (z.x + ex * t, z.y + ey * t), wd)

    # -- platform ---------------------------------------------------------
    def platform(self, z: ViewZone) -> None:
        """Slab with grass top, stone sides and decorations."""
        lay, p = self.lay, self.p
        th = THEMES[z.kind if z.kind in THEMES else "normal"]
        rng = random.Random(z.name)
        cx, cy = lay.center(z)
        hw, hh, T = lay.hw, lay.hw / 2, lay.T
        top, right = (cx, cy - hh), (cx + hw, cy)
        bot, left = (cx, cy + hh), (cx - hw, cy)
        def dn(q: Pt, d: float = T) -> Pt:
            return q[0], q[1] + d

        p.poly(rounded([left, bot, dn(bot), dn(left)], 0.05 * hw),
               th["left"], OUT, 3)
        p.poly(rounded([bot, right, dn(right), dn(bot)], 0.05 * hw),
               th["right"], OUT, 3)
        # stone seams
        for face, (e0, e1) in ((th["left"], (left, bot)),
                               (th["right"], (bot, right))):
            seam = shade(face, 0.82)
            p.line([dn(e0, T * .55), dn(e1, T * .55)], seam, 1.6)
            for row, y0 in ((0, .1), (1, .55)):
                k = 3 if row == 0 else 2
                for i in range(1, k + 1):
                    t = (i + rng.uniform(-.2, .2) + 0.5 * row) / (k + 1)
                    q = lerp_pt(e0, e1, min(.92, max(.08, t)))
                    p.line([dn(q, T * y0 + 6), dn(q, T * (y0 + .45))],
                           seam, 1.6)
        # grass lip with drips
        for e0, e1 in ((left, bot), (bot, right)):
            n = 18
            ph = rng.uniform(0, 6)
            upper = [lerp_pt(e0, e1, i / n) for i in range(n + 1)]
            lower = [dn(q, T * (0.20 + 0.10 * math.sin(i * 1.7 + ph)))
                     for i, q in enumerate(upper)]
            p.poly(upper + lower[::-1], th["lip"])
        # top surface
        shape = rounded([top, right, bot, left], 0.10 * hw, 6)
        p.poly(shape, th["top"], OUT, 3)
        for _ in range(7):
            u, v = rng.uniform(-.3, .3), rng.uniform(-.3, .3)
            c = self.g(z, u, v)
            p.ellipse(c[0], c[1], hw * rng.uniform(.10, .2),
                      hw * rng.uniform(.05, .1), th["patch"])
        for i in (1, 2, 3):
            f = -.5 + i / 4
            p.line([self.g(z, f, -.5), self.g(z, f, .5)],
                   shade(th["top"], .93), 1.2)
            p.line([self.g(z, -.5, f), self.g(z, .5, f)],
                   shade(th["top"], .93), 1.2)
        p.poly(shape, None, OUT, 3)
        if z.kind == "restricted":
            for _ in range(4):
                c = (rng.uniform(-.3, .3), rng.uniform(-.3, .3))
                pts = [self.g(z, c[0] + k * .08 * rng.choice((1, -1)),
                              c[1] + k * .1) for k in range(4)]
                p.line(pts, (255, 176, 80), 2.4)
        self.top_paths(z)
        if z.kind == "priority":
            for u, v, r in ((-.3, -.1, 1), (.1, -.32, .7), (.3, .12, .9)):
                x, y = self.g(z, u, v)
                r *= hw * .07
                p.poly([(x, y - r), (x + r * .28, y - r * .28), (x + r, y),
                        (x + r * .28, y + r * .28), (x, y + r),
                        (x - r * .28, y + r * .28), (x - r, y),
                        (x - r * .28, y - r * .28)], (255, 252, 196))
        self.decor(z, rng)

    # -- pad --------------------------------------------------------------
    def pad(self, z: ViewZone) -> None:
        """Coloured landing pad in the middle of the platform."""
        p, hw = self.p, self.lay.hw
        base = zone_color(z.color) if z.color else (
            (118, 214, 80) if z.role == "start" else
            (240, 96, 108) if z.role == "end" else NEUTRAL)
        big = z.role in ("start", "end")
        ph = hw * (0.36 if big else 0.30)
        th = ph * 0.26
        cx, cy = self.lay.center(z)
        cy -= th * 0.4

        def diamond(q: float) -> list[Pt]:
            return [(cx, cy - q / 2), (cx + q, cy), (cx, cy + q / 2),
                    (cx - q, cy)]
        if big:
            p.poly(rounded(diamond(ph * 1.35), ph * .2),
                   shade(base, 1.45), shade(base, .8), 2)
        d0, d1 = diamond(ph), [(x, y + th) for x, y in diamond(ph)]
        p.poly(rounded([d0[3], d0[2], d1[2], d1[3]], ph * .1),
               shade(base, .72), shade(base, .55), 2)
        p.poly(rounded([d0[2], d0[1], d1[1], d1[2]], ph * .1),
               shade(base, .85), shade(base, .55), 2)
        p.poly(rounded(d0, ph * .22), base, shade(base, .6), 2.2)
        p.poly(rounded(diamond(ph * .62), ph * .15), shade(base, 1.18))

    # -- decorations ------------------------------------------------------
    def decor(self, z: ViewZone, rng: random.Random) -> None:
        """Pick decorations for a platform and register them."""
        k = self.lay.hw
        dirs = self.neighbours(z)
        spots = [(-.34, -.34), (.34, -.34), (-.34, .34), (.36, .36),
                 (-.40, 0), (0, -.40), (.40, 0), (0, .40),
                 (-.2, -.4), (-.4, -.2), (.2, -.4), (.4, -.2),
                 (-.4, .2), (-.2, .4), (.4, .2), (.2, .4)]
        free = []
        for u, v in spots:
            if math.hypot(u, v) < 0.26 and z.kind != "blocked":
                continue
            ok = True
            for ex, ey in dirs:
                proj = u * ex + v * ey
                if proj > 0 and math.hypot(u - proj * ex,
                                           v - proj * ey) < 0.24:
                    ok = False
            if ok:
                free.append((u, v))
        rng.shuffle(free)
        items: list[tuple[float, Callable[[], None]]] = []

        def add(u: float, v: float, fn: Callable[[float, float, float],
                                                 None]) -> None:
            x, y = self.g(z, u, v)
            items.append((y, lambda: fn(x, y, k)))
        if z.kind == "blocked":
            for u, v in [(0, 0)] + free[:4]:
                add(u, v, self.big_rock(rng.uniform(1.3, 1.8), rng))
        else:
            # tall things only behind the pad, so pads always stay visible
            back = [s for s in free if s[0] + s[1] < -.1]
            front = [s for s in free if s not in back]
            if rng.random() < 0.55 and back:
                u, v = back.pop(0)
                add(u, v, rng.choice((self.house, self.tower, self.igloo)))
            for u, v in back[:rng.randint(1, 3)]:
                add(u, v, getattr(self, rng.choice(("tree", "tree",
                                                    "bush", "fern"))))
            for u, v in front[:rng.randint(2, 4)]:
                add(u, v, getattr(self, rng.choice(("bush", "flower",
                                                    "flower", "fern",
                                                    "rock"))))
        if z.kind != "blocked":
            items.append((self.lay.center(z)[1], lambda: self.pad(z)))
        for _, fn in sorted(items, key=lambda it: it[0]):
            fn()

    def tree(self, x: float, y: float, k: float) -> None:
        """Round cartoon tree."""
        p = self.p
        r = 0.2 * k
        g = (88, 170, 66)
        p.ellipse(x, y, r * 1.1, r * .42, (120, 170, 60))
        p.poly([(x - .035 * k, y), (x + .035 * k, y),
                (x + .03 * k, y - .17 * k), (x - .03 * k, y - .17 * k)],
               (120, 84, 60), OUT, 1.5)
        cy = y - .17 * k - r * .8
        p.ellipse(x, cy + r * .2, r, r * .95, shade(g, .72), OUT, 1.6)
        p.ellipse(x - r * .5, cy, r * .62, r * .6, g, OUT, 1.6)
        p.ellipse(x + r * .45, cy + r * .05, r * .6, r * .6, g, OUT, 1.6)
        p.ellipse(x, cy - r * .3, r * .78, r * .72, shade(g, 1.08))
        p.ellipse(x - r * .3, cy - r * .5, r * .28, r * .22, shade(g, 1.4))

    def bush(self, x: float, y: float, k: float) -> None:
        """Small round bush."""
        p, r = self.p, 0.11 * k
        g = (96, 178, 70)
        for dx, dy, s in ((-.8, 0, .8), (.8, 0, .8), (0, -.5, 1)):
            p.ellipse(x + dx * r, y + dy * r - r * .5, r * s, r * s * .9,
                      g if dy else shade(g, .85), OUT, 1.4)
        p.ellipse(x - r * .2, y - r * 1.3, r * .35, r * .25,
                  shade(g, 1.4))

    def rock(self, x: float, y: float, k: float,
             rng: Optional[random.Random] = None) -> None:
        """Grey boulder."""
        rng = rng or random.Random(int(x * 7 + y))
        r = 0.12 * k
        pts = [(x + math.cos(a) * r * rng.uniform(.85, 1.1),
                y - r * .55 + math.sin(a) * r * .75 * rng.uniform(.85, 1.1))
               for a in [i * math.pi / 3.5 for i in range(7)]]
        self.p.poly(rounded(pts, r * .5), (150, 150, 164), OUT, 1.8)
        hl = [(x - r * .1 + math.cos(a) * r * .55,
               y - r * .85 + math.sin(a) * r * .38)
              for a in [i * math.pi / 3 for i in range(6)]]
        self.p.poly(rounded(hl, r * .3), (186, 186, 198))

    def big_rock(self, scale: float, rng: random.Random
                 ) -> Callable[[float, float, float], None]:
        """Return a drawer for an oversized boulder (blocked zones)."""
        def draw(x: float, y: float, k: float) -> None:
            self.rock(x, y, k * scale, rng)
        return draw

    def flower(self, x: float, y: float, k: float) -> None:
        """Three tiny white flowers."""
        r = 0.022 * k
        for dx, dy in ((-2.2, 0.4), (0, -0.6), (2.0, 0.5)):
            fx, fy = x + dx * r * 2, y + dy * r * 2
            for a in range(5):
                ang = a * 2 * math.pi / 5
                self.p.ellipse(fx + math.cos(ang) * r * 1.3,
                               fy + math.sin(ang) * r * 1.0,
                               r, r * .8, (252, 252, 252))
            self.p.ellipse(fx, fy, r * .8, r * .7, (250, 205, 70))

    def fern(self, x: float, y: float, k: float) -> None:
        """Spiky leaf plant."""
        r = 0.16 * k
        for i, a in enumerate((-70, -35, 0, 35, 70, -105, 105)):
            ang = math.radians(a - 90)
            tip = (x + math.cos(ang) * r * 1.1,
                   y + math.sin(ang) * r * .9 - r * .2)
            nx, ny = -math.sin(ang), math.cos(ang)
            mid = (x + math.cos(ang) * r * .55, y + math.sin(ang) * r * .5)
            col = (76 + 14 * (i % 3), 164 + 8 * (i % 2), 70)
            self.p.poly([(x, y), (mid[0] + nx * r * .22,
                                  mid[1] + ny * r * .2), tip,
                         (mid[0] - nx * r * .22, mid[1] - ny * r * .2)],
                        col, OUT, 1.2)

    def cube(self, x: float, y: float, a: float, hgt: float) -> None:
        """Small iso building with windows."""
        p = self.p
        p.poly([(x - a, y), (x, y + a / 2), (x, y + a / 2 - hgt),
                (x - a, y - hgt)], (196, 198, 212), OUT, 1.6)
        p.poly([(x, y + a / 2), (x + a, y), (x + a, y - hgt),
                (x, y + a / 2 - hgt)], (222, 224, 236), OUT, 1.6)
        p.poly([(x - a, y - hgt), (x, y + a / 2 - hgt),
                (x + a, y - hgt), (x, y - a / 2 - hgt)],
               (240, 242, 250), OUT, 1.6)
        for sx, f in ((1, .55), (-1, .5)):
            wx = x + sx * a * f
            wy = y + a * (.5 - f * .5) - hgt * .5
            p.poly([(wx - a * .12, wy - a * .12 * (-sx) - a * .1),
                    (wx + a * .12, wy + a * .12 * (-sx) - a * .1),
                    (wx + a * .12, wy + a * .12 * (-sx) + a * .2),
                    (wx - a * .12, wy - a * .12 * (-sx) + a * .2)],
                   (96, 170, 230), OUT, 1)

    def house(self, x: float, y: float, k: float) -> None:
        """Two stacked cubes, like in the reference picture."""
        a = 0.16 * k
        self.cube(x - a * .6, y, a, a * 1.0)
        self.cube(x + a * .9, y - a * .3, a * .8, a * 1.5)

    def tower(self, x: float, y: float, k: float) -> None:
        """Round stone tower with a dark crown."""
        p, r, hgt = self.p, 0.12 * k, 0.55 * k
        body = (226, 218, 228)
        p.ellipse(x, y, r, r * .45, shade(body, .8), OUT, 1.8)
        p.poly([(x - r, y), (x + r, y), (x + r, y - hgt),
                (x - r, y - hgt)], body)
        p.poly([(x + r * .1, y + r * .45), (x + r, y), (x + r, y - hgt),
                (x + r * .1, y - hgt + r * .45)], (186, 178, 198))
        for f in (.2, .45):  # stone courses
            p.line([(x - r, y - hgt * f), (x, y - hgt * f + r * .45),
                    (x + r, y - hgt * f)], (170, 162, 182), 1.4)
        p.ellipse(x, y, r, r * .45, None, OUT, 1.8)
        p.line([(x - r, y), (x - r, y - hgt)], OUT, 1.8)
        p.line([(x + r, y), (x + r, y - hgt)], OUT, 1.8)
        p.poly([(x + r * .15, y - hgt * .30), (x + r * .45, y - hgt * .26),
                (x + r * .45, y - hgt * .56), (x + r * .15, y - hgt * .6)],
               (58, 56, 72))
        top = y - hgt * .78
        p.ellipse(x, top, r * 1.12, r * .52, (74, 72, 92), OUT, 1.8)
        p.poly([(x - r * 1.12, top), (x + r * 1.12, top),
                (x + r * 1.12, y - hgt), (x - r * 1.12, y - hgt)],
               (74, 72, 92))
        p.line([(x - r * 1.12, top), (x - r * 1.12, y - hgt)], OUT, 1.8)
        p.line([(x + r * 1.12, top), (x + r * 1.12, y - hgt)], OUT, 1.8)
        p.ellipse(x, y - hgt, r * 1.12, r * .52, (96, 94, 118), OUT, 1.8)
        p.ellipse(x, y - hgt, r * .78, r * .33, (156, 154, 176))

    def igloo(self, x: float, y: float, k: float) -> None:
        """White dome with a dark doorway."""
        p, r = self.p, 0.2 * k
        dome = [(x + math.cos(math.pi * i / 16) * r,
                 y - math.sin(math.pi * i / 16) * r * .9)
                for i in range(17)]
        p.poly(dome, (240, 244, 252), OUT, 1.8)
        right = [(x, y), *[(x + math.cos(math.pi * i / 16) * r,
                            y - math.sin(math.pi * i / 16) * r * .9)
                           for i in range(0, 9)]]
        p.poly(right, (214, 222, 240))
        p.line([(x - r, y), (x + r, y)], OUT, 1.8)
        for a in (.35, .7):
            p.line([(x + math.cos(math.pi * a) * r * .98,
                     y - math.sin(math.pi * a) * r * .88),
                    (x + math.cos(math.pi * a) * r * .6,
                     y - math.sin(math.pi * a) * r * .55)],
                   (196, 206, 228), 1.4)
        door = [(x - r * .32 + math.cos(math.pi * i / 8) * r * .32,
                 y + r * .02 - math.sin(math.pi * i / 8) * r * .4)
                for i in range(9)]
        p.poly(door, (58, 62, 82), OUT, 1.2)

    # -- labels -----------------------------------------------------------
    def label(self, z: ViewZone) -> None:
        """Name plaque below a platform."""
        p, lay = self.p, self.lay
        cx, cy = lay.center(z)
        size = int(max(11, min(22, lay.hw * 0.13)))
        y = cy + lay.hw / 2 + lay.T + size * 1.35
        parts = [{"start": "START", "end": "GOAL"}.get(z.role, "")]
        if z.kind != "normal":
            parts.append(z.kind.upper())
        if z.cap > 1 and z.role == "hub":
            parts.append(f"MAX {z.cap}")
        tag = " · ".join(t for t in parts if t)
        txt = z.name
        wd = max(p.measure(txt, size), p.measure(tag, size - 4)
                 if tag else 0) + size * 1.2
        ht = size * (2.1 if tag else 1.5)
        box = [(cx - wd / 2, y - ht / 2), (cx + wd / 2, y - ht / 2),
               (cx + wd / 2, y + ht / 2), (cx - wd / 2, y + ht / 2)]
        p.poly(rounded(box, size * .5, 4), (252, 252, 254), (190, 190, 204),
               2)
        ty = y - (size * .38 if tag else 0)
        p.text(cx, ty, txt, size, (52, 50, 66))
        if tag:
            col = ((80, 170, 60) if tag.startswith("START") else
                   (220, 80, 90) if tag.startswith("GOAL") else
                   (176, 90, 76) if "RESTRICTED" in tag else
                   (60, 160, 70) if "PRIORITY" in tag else (120, 120, 134))
            p.text(cx, y + size * .62, tag, size - 4, col)


# --------------------------------------------------------------------------
# Background and static base image
# --------------------------------------------------------------------------
def gradient(w: int, h: int) -> Image.Image:
    """Soft white-to-lavender background."""
    col = Image.linear_gradient("L").resize((w, h))
    top, bot = Image.new("RGB", (w, h), (253, 252, 254)), Image.new(
        "RGB", (w, h), (238, 240, 248))
    return Image.composite(bot, top, col)


def doodles(w: int, h: int) -> Image.Image:
    """Faint hand-drawn space doodles in the background."""
    p, rng = Painter(w, h), random.Random(11)
    ink: RGB = (222, 224, 232)
    for _ in range(5):
        x, y, r = rng.uniform(0, w), rng.uniform(0, h), rng.uniform(26, 56)
        p.ellipse(x, y, r, r, None, ink, 2.4)
        p.ellipse(x, y, r * 1.9, r * .45, None, ink, 2.2)
    for _ in range(26):
        x, y, r = rng.uniform(0, w), rng.uniform(0, h), rng.uniform(7, 15)
        pts = [(x + math.cos(a * 2 * math.pi / 10 - math.pi / 2) * r *
                (1 if a % 2 == 0 else .45),
                y + math.sin(a * 2 * math.pi / 10 - math.pi / 2) * r *
                (1 if a % 2 == 0 else .45)) for a in range(10)]
        p.poly(pts, None, ink, 2)
    for _ in range(7):
        x, y = rng.uniform(0, w), rng.uniform(0, h)
        p.ellipse(x, y, 9, 7, None, ink, 2.4)
        p.line([(x + 8, y), (x + 8, y - 30), (x + 20, y - 24)], ink, 2.4)
    for _ in range(5):
        x, y = rng.uniform(0, w), rng.uniform(0, h)
        for dx, dy, r in ((0, 0, 20), (22, 6, 16), (-20, 8, 14)):
            p.ellipse(x + dx, y + dy, r, r * .8, None, ink, 2.2)
    return p.done()


def build_base(scene: ViewScene, lay: Layout, w: int, h: int,
               background: bool = True, labels: bool = True) -> Image.Image:
    """Render background, shadows, bridges and platforms once.

    With ``background=False`` the result is a transparent RGBA picture
    (used for the small map previews of the menu).
    """
    if background:
        base = gradient(w, h).convert("RGBA")
        base = Image.alpha_composite(base, doodles(w, h))
    else:
        base = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    sh = Painter(w, h)
    for z in scene.zones.values():
        cx, cy = lay.center(z)
        hw, hh, off = lay.hw, lay.hw / 2, lay.T + 0.10 * lay.hw
        sh.poly([(cx, cy - hh + off), (cx + hw, cy + off),
                 (cx + hw, cy + off + lay.T * .6),
                 (cx, cy + hh + off + lay.T * .6),
                 (cx - hw, cy + off + lay.T * .6), (cx - hw, cy + off)],
                (70, 60, 100, 70))
    blur = 14.0 if background else max(1.5, lay.hw * 0.12)
    shadow = sh.done().filter(ImageFilter.GaussianBlur(blur))
    base = Image.alpha_composite(base, shadow)
    art = Art(scene, lay, w, h)
    art.p.k = 1.0 if background else max(0.3, min(1.0, lay.hw / 100))
    art.ribbons()
    for z in sorted(scene.zones.values(), key=lambda q: q.x + q.y):
        art.platform(z)
    if labels:
        for z in sorted(scene.zones.values(), key=lambda q: q.x + q.y):
            art.label(z)
    out = Image.alpha_composite(base, art.p.done())
    return out.convert("RGB") if background else out
