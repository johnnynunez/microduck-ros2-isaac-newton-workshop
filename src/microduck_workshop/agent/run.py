"""Portable workshop entrypoint: python -m microduck_workshop.agent.run."""

from .runner import main

if __name__ == "__main__":
    raise SystemExit(main())
