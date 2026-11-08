"""`python -m equion <명령>` — 명령줄 진입점(equion.cli)."""
import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
