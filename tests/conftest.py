"""Shared test setup: achievements are saved in a temporary folder, never in the real save."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "game"))

import achievements  # noqa: E402


@pytest.fixture(autouse=True)
def private_achievements(tmp_path, monkeypatch):
    monkeypatch.setattr(achievements, "PATH", str(tmp_path / "achievements.json"))
