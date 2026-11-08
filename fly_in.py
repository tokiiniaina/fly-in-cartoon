"""Entry point: ``python3 fly_in.py [map] [--text|--png F|--gif F]``."""

import sys

from flyin.src.app import Application


def main() -> int:
    """Run the application."""
    return Application().run()


if __name__ == "__main__":
    sys.exit(main())
