"""Exceptions raised by the Fly-in engine."""


class FlyInError(Exception):
    """Base class for engine errors."""


class NoPathError(FlyInError):
    """Raised when no route exists from start to end."""


class SimulationError(FlyInError):
    """Raised when a plan breaks a rule at a given turn."""

    def __init__(self, turn: int, message: str) -> None:
        """Store the turn number and build the error message."""
        super().__init__(f"turn {turn}: {message}")

        self.turn = turn
