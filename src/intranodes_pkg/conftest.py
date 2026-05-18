"""
Pytest fixtures and bootstrap for intranodes_pkg tests.
"""

import os
from pathlib import Path


def _find_project_root(start: Path) -> Path:
    for parent in (start, *start.parents):
        if (parent / ".env").is_file():
            return parent
    raise RuntimeError(f"Could not find .env walking up from {start}")


os.chdir(_find_project_root(Path(__file__).resolve()))
