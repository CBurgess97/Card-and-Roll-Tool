"""Shared fixtures for dice-cards tests."""

from pathlib import Path

import pytest

EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "schema" / "examples"


@pytest.fixture
def examples_dir():
    """Return the path to the schema examples directory."""
    return EXAMPLES_DIR


def example_path(name: str) -> str:
    """Return the full path to an example file as a string."""
    return str(EXAMPLES_DIR / name)
