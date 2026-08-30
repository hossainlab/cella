"""Scaffold smoke tests: imports resolve and config loads.

These only exercise the light base environment (no pipeline/api groups needed).
"""

from __future__ import annotations

from cella import __version__
from cella.core.config import ORGANS, settings


def test_version() -> None:
    assert __version__ == "0.1.0"


def test_organs_count() -> None:
    assert len(ORGANS) == 12


def test_settings_defaults() -> None:
    assert settings.processed_dir.name == "processed"
