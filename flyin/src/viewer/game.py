"""The game: menu, map selection and play screens (no window code).

The class only turns events into state and state into a Pillow image, so
it runs (and is tested) without any window. ``app.py`` plugs pygame on it.
"""

from __future__ import annotations

import math
import threading
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw

from flyin.src.engine.solver import Solution, solve
from flyin.src.map_data import MapData
from flyin.src.parser_function import MapParser
from flyin.src.viewer import ui
from flyin.src.viewer.art import Layout, build_base, doodles, gradient
from flyin.src.viewer.catalog import (MapEntry, find_maps, load_scores,
                                      pretty, save_score, stars)
from flyin.src.viewer.draw import RGB, font
from flyin.src.viewer.model import (ViewScene, parse_moves,
                                    scene_from_map)
from flyin.src.viewer.renderer import Renderer

W, H = 1280, 720
Rect = tuple[int, int, int, int]
SPEEDS = (0.5, 0.8, 1.2, 2.0, 3.0, 5.0)
COLS, ROWS = 4, 3
CARD_W, CARD_H, GAP = 290, 170, 20


@dataclass
class Loaded:
    """A map entry with its parsed data (or the error that broke it)."""

    entry: MapEntry
    data: MapData | None = None
    scene: ViewScene | None = None
    error: str = ""
    thumb: Image.Image | None = None


class Game:
    """State machine of the game: menu, select, loading, play."""

    def __init__(self, maps_root: Path | None = None,
                 threaded: bool = True) -> None:
        """Parse every map and show the main menu."""
        self.threaded = threaded
        self.items = [self._load(e) for e in find_maps(maps_root)]
        self.scores = load_scores()
        self.state = "menu"
        self.page = 0
        self.quit = False
        self.buttons: list[tuple[Rect, str]] = []
        self.hover = ""
        self.toast = ""
        self.toast_left = 0.0
        self.clock = 0.0
        self.bg = Image.alpha_composite(
            gradient(W, H).convert("RGBA"), doodles(W, H))
        self.cache: dict[tuple[object, ...], Image.Image] = {}
        self.demo: Renderer | None = None
        self.demo_tau = 0.0
        self.current: Loaded | None = None
        self.rend: Renderer | None = None
        self.solution: Solution | None = None
        self.tau = 0.0
        self.playing = False
        self.speed = 2
        self.finished = False
        self._job: threading.Thread | None = None
        self._result: tuple[Renderer, Solution] | str | None = None
        self._build_demo()

    # -- loading ----------------------------------------------------------
    @staticmethod
    def _load(entry: MapEntry) -> Loaded:
        """Parse a map and prepare its thumbnail."""
        item = Loaded(entry)
        try:
            item.data = MapParser().parse(str(entry.path))
            item.scene = scene_from_map(item.data)
        except (ValueError, OSError) as error:
            item.error = str(error)
            return item
        lay = Layout(item.scene, 270, 100, margins=(6, 6, 8), max_hw=40)
        item.thumb = build_base(item.scene, lay, 270, 100,
                                background=False, labels=False)
        return item

    def _build_demo(self) -> None:
        """Prepare the animation that plays behind the main menu."""
        for item in self.items:
            if item.entry.path.stem == "02_simple_fork" and item.data \
                    and item.scene:
                sol = solve(item.data)
                self.demo = Renderer(
                    item.scene, parse_moves(sol.lines), sol.lines, W, H,
                    margins=(70, 90, 300), dx=230)
                return

    def _start_job(self, item: Loaded) -> None:
        """Solve and render a map, in a thread when allowed."""
        self.current, self._result = item, None
        self.state = "loading"

        def work() -> None:
            try:
                assert item.data is not None and item.scene is not None
                sol = solve(item.data)
                rend = Renderer(item.scene, parse_moves(sol.lines),
                                sol.lines, W, H, title=item.entry.title,
                                target=item.entry.record)
                self._result = (rend, sol)
            except (ValueError, AssertionError) as error:
                self._result = str(error)

        if self.threaded:
            self._job = threading.Thread(target=work, daemon=True)
            self._job.start()
        else:
            work()
            self._poll()

    def _poll(self) -> None:
        """Pick up the result of the background job."""
        res = self._result
        if res is None:
            return
        self._result = None
        if isinstance(res, str):
            self.say(f"Cannot solve: {res}")
            self.state = "select"
            return
        self.rend, self.solution = res
        self.tau, self.playing, self.finished = 0.0, True, False
        self.state = "play"

    def open_path(self, path: str) -> None:
        """Open any map file directly in the play screen."""
        item = self._load(MapEntry(Path(path), "custom",
                                   pretty(Path(path).stem)))
        if item.error:
            self.say(f"Invalid map: {item.error}")
            self.state = "select"
            return
        self._start_job(item)

    def say(self, text: str) -> None:
        """Show a short message at the bottom of the screen."""
        self.toast, self.toast_left = text, 4.0

    # -- events -----------------------------------------------------------
    def on_move(self, x: int, y: int) -> None:
        """Remember which button is under the mouse."""
        self.hover = self._hit(x, y)

    def _hit(self, x: int, y: int) -> str:
        """Action of the topmost button at a point."""
        for (bx, by, bw, bh), action in reversed(self.buttons):
            if bx <= x < bx + bw and by <= y < by + bh:
                return action
        return ""

    def on_click(self, x: int, y: int) -> None:
        """Run the action of the clicked button."""
        action = self._hit(x, y)
        if action:
            self.act(action)

    def on_key(self, key: str) -> None:
        """Keyboard shortcuts (names such as 'space', 'left')."""
        if self.state == "menu" and key in ("return", "space"):
            self.act("goto:select")
        elif self.state == "select" and key == "escape":
            self.act("goto:menu")
        elif self.state == "play":
            table = {"space": "toggle", "left": "prev", "right": "next",
                     "r": "restart", "escape": "goto:select",
                     "up": "faster", "down": "slower"}
            if key in table:
                self.act(table[key])

    def act(self, action: str) -> None:
        """Apply one named action."""
        if action.startswith("goto:"):
            self.state = action[5:]
            self.page = 0 if self.state == "select" else self.page
        elif action == "quit":
            self.quit = True
        elif action.startswith("map:"):
            item = self.items[int(action[4:])]
            if item.error:
                self.say(f"Invalid map: {item.error}")
            else:
                self._start_job(item)
        elif action == "pagenext":
            self.page = min(self.page + 1, self._pages() - 1)
        elif action == "pageprev":
            self.page = max(self.page - 1, 0)
        elif self.rend is not None:
            self._play_action(action)

    def _play_action(self, action: str) -> None:
        """Actions of the play screen."""
        assert self.rend is not None
        total = float(self.rend.T)
        if action == "toggle":
            if self.tau >= total:
                self.tau, self.finished = 0.0, False
            self.playing = not self.playing
        elif action == "restart":
            self.tau, self.playing, self.finished = 0.0, True, False
        elif action in ("prev", "next"):
            self.playing, self.finished = False, False
            base = math.floor(self.tau + 1e-6) if action == "next" \
                else math.ceil(self.tau - 1e-6)
            self.tau = max(0.0, min(total, base + (1 if action == "next"
                                                   else -1)))
        elif action == "faster":
            self.speed = min(self.speed + 1, len(SPEEDS) - 1)
        elif action == "slower":
            self.speed = max(self.speed - 1, 0)
        elif action == "nextmap":
            self._next_map()

    def _next_map(self) -> None:
        """Go to the next playable map of the list."""
        if self.current is None:
            return
        idx = next((i for i, it in enumerate(self.items)
                    if it.entry.key == self.current.entry.key), -1)
        for step in range(1, len(self.items) + 1):
            item = self.items[(idx + step) % len(self.items)]
            if not item.error:
                self._start_job(item)
                return
        self.state = "select"

    def _pages(self) -> int:
        """Number of pages of the selection screen."""
        return max(1, math.ceil(len(self.items) / (COLS * ROWS)))

    # -- time -------------------------------------------------------------
    def update(self, dt: float) -> None:
        """Advance animations by ``dt`` seconds."""
        self.clock += dt
        self.toast_left = max(0.0, self.toast_left - dt)
        if self.state == "loading":
            self._poll()
        if self.state == "menu" and self.demo is not None:
            self.demo_tau += dt * 1.1
            if self.demo_tau > self.demo.T + 2.5:
                self.demo_tau = 0.0
        if self.state == "play" and self.rend is not None and self.playing:
            self.tau = min(float(self.rend.T),
                           self.tau + dt * SPEEDS[self.speed])
            if self.tau >= self.rend.T and not self.finished:
                self.finished, self.playing = True, False
                self._record()

    def _record(self) -> None:
        """Save the result when a map is completed."""
        if self.current is None or self.solution is None:
            return
        if self.current.entry.level == "custom":
            return
        save_score(self.current.entry.key, self.solution.turns)
        self.scores = load_scores()

    # -- drawing ----------------------------------------------------------
    def render(self) -> Image.Image:
        """Draw the current screen and rebuild the button list."""
        self.buttons = []
        if self.state == "play" and self.rend is not None:
            img = self._draw_play(self.rend)
        elif self.state == "select":
            img = self._draw_select()
        elif self.state == "loading":
            img = self._draw_loading()
        else:
            img = self._draw_menu()
        if self.toast_left > 0:
            self._draw_toast(img)
        return img.convert("RGB")

    def _button(self, img: Image.Image, rect: Rect, action: str,
                color: RGB, text: str = "", size: int = 22,
                icon: str = "") -> None:
        """Draw a button and register its hit area."""
        x, y, w, h = rect
        spr = ui.pill(w, h, color, text, size, self.hover == action, icon)
        ui.blit(img, spr, x, y)
        self.buttons.append((rect, action))

    def _draw_toast(self, img: Image.Image) -> None:
        """Message pill at the bottom centre."""
        f = font(17)
        text = self.toast if len(self.toast) < 90 else \
            self.toast[:87] + "..."
        wd = int(f.getlength(text)) + 40
        d = ImageDraw.Draw(img, "RGBA")
        d.rounded_rectangle([W / 2 - wd / 2, H - 90, W / 2 + wd / 2,
                             H - 48], 21, fill=(52, 50, 66, 240))
        d.text((W / 2, H - 69), text, font=f, fill=(255, 255, 255),
               anchor="mm")

    def _draw_menu(self) -> Image.Image:
        """Title screen with a live demo behind it."""
        if self.demo is not None:
            img = self.demo.frame(self.demo_tau, self.clock,
                                  hud=False).convert("RGBA")
            veil = Image.linear_gradient("L").rotate(90).resize((W, H))
            veil = veil.point(lambda v: 255 - v if v > 90 else 165)
            img.alpha_composite(Image.merge(
                "RGBA", (*Image.new("RGB", (W, H), (253, 252, 254)).split(),
                         veil.point(lambda v: min(v, 235)))))
        else:
            img = self.bg.copy()
        d = ImageDraw.Draw(img, "RGBA")
        bob = math.sin(self.clock * 2.0) * 4
        d.text((84, 150 + bob), "FLY-IN", font=font(112),
               fill=(52, 50, 66), stroke_width=0)
        d.text((88, 270), "Guide the whole fleet to the goal,",
               font=font(24), fill=(100, 100, 124))
        d.text((88, 302), "in as few turns as possible.",
               font=font(24), fill=(100, 100, 124))
        self._button(img, (88, 370, 300, 76), "goto:select", ui.BLUE,
                     "PLAY", 32)
        self._button(img, (88, 468, 300, 60), "quit", ui.RED, "QUIT", 24)
        cleared = sum(1 for i in self.items if i.entry.key in self.scores)
        ok = sum(1 for i in self.items if not i.error)
        d.text((92, 566), f"Maps cleared  {cleared} / {ok}", font=font(18),
               fill=(130, 130, 148))
        return img

    def _thumb_card(self, idx: int) -> Image.Image:
        """The (cached) card of the map number ``idx``."""
        item = self.items[idx]
        key = item.entry.key
        best = self.scores.get(key, 0)
        ref = item.entry.record or best
        star = stars(best, ref, item.entry.record) if best else 0
        hov = self.hover == f"map:{idx}"
        ck: tuple[object, ...] = ("card", key, hov, best)
        if ck not in self.cache:
            self.cache[ck] = ui.card(
                CARD_W, CARD_H, item.thumb, item.entry.title,
                item.entry.level,
                item.data.nb_drones if item.data else 0, best, star,
                hov, item.error)
        return self.cache[ck]

    def _draw_select(self) -> Image.Image:
        """Grid of map cards."""
        img = self.bg.copy()
        d = ImageDraw.Draw(img)
        d.text((40, 52), "Choose a map", font=font(40), fill=ui.INK,
               anchor="lm")
        self._button(img, (W - 150, 28, 110, 48), "goto:menu", ui.RED,
                     "BACK", 18)
        pages = self._pages()
        if pages > 1:
            d.text((W - 250, 52), f"{self.page + 1}/{pages}",
                   font=font(18), fill=ui.MUTED, anchor="mm")
            self._button(img, (W - 330, 28, 48, 48), "pageprev", ui.BLUE,
                         icon="left")
            self._button(img, (W - 220, 28, 48, 48), "pagenext", ui.BLUE,
                         icon="right")
        per = COLS * ROWS
        for slot, idx in enumerate(range(self.page * per, min(
                len(self.items), (self.page + 1) * per))):
            cx = 40 + (slot % COLS) * (CARD_W + GAP)
            cy = 110 + (slot // COLS) * (CARD_H + GAP)
            ui.blit(img, self._thumb_card(idx), cx, cy)
            self.buttons.append(((cx, cy, CARD_W, CARD_H), f"map:{idx}"))
        return img

    def _draw_loading(self) -> Image.Image:
        """Spinner shown while a map is solved and rendered."""
        img = self.bg.copy()
        d = ImageDraw.Draw(img)
        name = self.current.entry.title if self.current else ""
        d.text((W / 2, H / 2 - 70), name, font=font(34), fill=ui.INK,
               anchor="mm")
        d.text((W / 2, H / 2 + 70), "Planning the flights...",
               font=font(20), fill=ui.MUTED, anchor="mm")
        for i in range(8):
            a = self.clock * 6 + i * math.pi / 4
            r = 6 + 3 * ((i - self.clock * 8) % 8) / 8
            d.ellipse([W / 2 + math.cos(a) * 34 - r,
                       H / 2 + math.sin(a) * 34 - r,
                       W / 2 + math.cos(a) * 34 + r,
                       H / 2 + math.sin(a) * 34 + r], fill=ui.BLUE)
        return img

    def _draw_play(self, rend: Renderer) -> Image.Image:
        """Animated map, control bar and the result card."""
        img = rend.frame(self.tau, self.clock).convert("RGBA")
        specs: list[tuple[str, str, int]] = [
            ("goto:select", "home", 44), ("restart", "restart", 44),
            ("prev", "prev", 44),
            ("toggle", "pause" if self.playing else "play", 52),
            ("next", "next", 44), ("slower", "minus", 36),
            ("", "", 56), ("faster", "plus", 36)]
        x = W - 24 - sum(s[2] for s in specs) - 10 * (len(specs) - 1)
        d = ImageDraw.Draw(img)
        for action, icon, size in specs:
            if not action:
                d.text((x + size / 2, 50), f"x{SPEEDS[self.speed]:g}",
                       font=font(18), fill=ui.INK, anchor="mm")
            else:
                color = ui.GREEN if action == "toggle" else ui.BLUE
                self._button(img, (x, 24 + (52 - size) // 2, size, size),
                             action, color, icon=icon)
            x += size + 10
        if self.finished and self.solution is not None:
            self._draw_result(img)
        return img

    def _draw_result(self, img: Image.Image) -> None:
        """Mission complete card."""
        assert self.solution is not None and self.current is not None
        veil = Image.new("RGBA", (W, H), (253, 252, 254, 120))
        img.alpha_composite(veil)
        w, h = 520, 360
        x, y = (W - w) // 2, (H - h) // 2 - 10
        ui.blit(img, ui.panel(w, h), x, y)
        d = ImageDraw.Draw(img)
        turns = self.solution.turns
        entry = self.current.entry
        ref = entry.record or turns
        star = stars(turns, turns, entry.record)
        d.text((W / 2, y + 50), "MISSION COMPLETE", font=font(34),
               fill=ui.INK, anchor="mm")
        d.text((W / 2, y + 100), entry.title, font=font(20),
               fill=ui.MUTED, anchor="mm")
        d.text((W / 2, y + 158), f"{turns} turns", font=font(52),
               fill=(70, 120, 220), anchor="mm")
        sp = ui.stars_sprite(star, 44)
        img.alpha_composite(sp, ((W - sp.width) // 2, y + 196))
        note = (f"Record to beat: {ref}" if entry.record
                else f"Solved by {self.solution.strategy}")
        d.text((W / 2, y + 268), note, font=font(16), fill=ui.MUTED,
               anchor="mm")
        by = y + h - 76
        self._button(img, (x + 30, by, 140, 52), "restart", ui.BLUE,
                     "REPLAY", 18)
        self._button(img, (x + 190, by, 140, 52), "nextmap", ui.GREEN,
                     "NEXT", 18)
        self._button(img, (x + 350, by, 140, 52), "goto:select", ui.RED,
                     "MAPS", 18)
