"""UI entry point (thin wrapper around the bootstrap application)."""
from __future__ import annotations

from app.bootstrap.application import run


def main() -> int:
    return run()


if __name__ == "__main__":
    raise SystemExit(main())
