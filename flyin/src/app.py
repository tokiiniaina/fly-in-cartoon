"""Command line and window loop of the Fly-in game."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from PIL import Image

from flyin.src.engine.solver import solve
from flyin.src.parser_function import MapParser
from flyin.src.viewer.game import H, W, Game
from flyin.src.viewer.model import parse_moves, scene_from_map
from flyin.src.viewer.renderer import Renderer, export_gif


class Application:
    """Parse the arguments and run the requested mode."""

    def __init__(self, argv: list[str] | None = None) -> None:
        """Read the command line."""
        parser = argparse.ArgumentParser(
            prog="fly_in.py",
            description="Fly-in: route a drone fleet through a network.")
        parser.add_argument("map", nargs="?",
                            help="map file (omit it to open the menu)")
        parser.add_argument("--text", action="store_true",
                            help="print the turns instead of opening "
                            "the game")
        parser.add_argument("--png", metavar="FILE",
                            help="save the final frame as an image")
        parser.add_argument("--gif", metavar="FILE",
                            help="save the animation as a GIF")
        self.args = parser.parse_args(argv)

    def run(self) -> int:
        """Run the chosen mode and return the exit code."""
        args = self.args
        try:
            if args.map and (args.text or args.png or args.gif):
                return self._batch(args.map)
            return self._window(args.map)
        except (ValueError, OSError) as error:
            print(f"Error: {error}", file=sys.stderr)
            return 1

    def _batch(self, path: str) -> int:
        """Solve a map and print or export the result."""
        data = MapParser().parse(path)
        sol = solve(data)
        if self.args.text:
            print("\n".join(sol.lines))
        if self.args.png or self.args.gif:
            rend = Renderer(scene_from_map(data), parse_moves(sol.lines),
                            sol.lines, title=Path(path).stem)
            if self.args.png:
                rend.frame(float(rend.T), 0.0).save(self.args.png)
            if self.args.gif:
                export_gif(rend, self.args.gif, 1.5)
        return 0

    @staticmethod
    def _window(path: str | None) -> int:
        """Open the game window (needs pygame)."""
        try:
            import pygame
        except ImportError:
            print("pygame is missing: pip install pygame-ce "
                  "(or use --text / --png / --gif)", file=sys.stderr)
            return 1
        pygame.init()
        screen = pygame.display.set_mode(
            (W, H), pygame.SCALED | pygame.RESIZABLE)
        pygame.display.set_caption("Fly-In")
        game = Game()
        if path:
            game.open_path(path)
        clock = pygame.time.Clock()
        names = {pygame.K_SPACE: "space", pygame.K_LEFT: "left",
                 pygame.K_RIGHT: "right", pygame.K_UP: "up",
                 pygame.K_DOWN: "down", pygame.K_ESCAPE: "escape",
                 pygame.K_RETURN: "return", pygame.K_r: "r"}
        last = time.time()
        while not game.quit:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    game.quit = True
                elif event.type == pygame.MOUSEMOTION:
                    game.on_move(*event.pos)
                elif event.type == pygame.MOUSEBUTTONDOWN \
                        and event.button == 1:
                    game.on_click(*event.pos)
                elif event.type == pygame.KEYDOWN \
                        and event.key in names:
                    game.on_key(names[event.key])
            now = time.time()
            game.update(min(0.1, now - last))
            last = now
            frame: Image.Image = game.render()
            surf = pygame.image.frombuffer(frame.tobytes(), frame.size,
                                           "RGB")
            screen.blit(surf, (0, 0))
            pygame.display.flip()
            clock.tick(60)
        pygame.quit()
        return 0
