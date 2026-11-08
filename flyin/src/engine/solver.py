"""Facade of the engine: solve a map with both strategies, keep the best."""

from dataclasses import dataclass

from flyin.src.engine.checker import OutputChecker
from flyin.src.engine.formatter import OutputFormatter
from flyin.src.engine.network import Network
from flyin.src.engine.scheduler import SpaceTimeScheduler
from flyin.src.engine.simulation import Simulation
from flyin.src.engine.simulator import Simulator
from flyin.src.map_data import MapData


@dataclass
class Solution:
    """The best valid output found for a map."""

    lines: list[str]
    strategy: str

    @property
    def turns(self) -> int:
        """Number of turns of the solution."""
        return len(self.lines)


def _greedy(data: MapData) -> list[str]:
    """Run the greedy turn-by-turn simulator."""
    return Simulator(data).run()


def _space_time(data: MapData) -> list[str]:
    """Run the space-time A* planner and replay its plan."""
    network = Network(data)
    network.validate()
    plan = SpaceTimeScheduler().plan(network)
    return OutputFormatter().lines(Simulation(network, plan).run())


STRATEGIES = (("space-time A*", _space_time), ("greedy", _greedy))


def solve(data: MapData) -> Solution:
    """Return the shortest output that the independent checker accepts.

    Raises:
        ValueError: If no strategy gives a valid output.
    """
    best: Solution | None = None
    errors: list[str] = []
    for name, strategy in STRATEGIES:
        try:
            lines = strategy(data)
            OutputChecker(data).check(lines)
        except Exception as error:  # a strategy failing is not fatal
            errors.append(f"{name}: {error}")
            continue
        if best is None or len(lines) < best.turns:
            best = Solution(lines, name)
    if best is None:
        raise ValueError("; ".join(errors))
    return best
