"""Shared test setup."""

import pytest

from aqrgen import presets


@pytest.fixture(autouse=True)
def presets_dir(tmp_path, monkeypatch):
    """Keep every test away from the real per-user presets folder."""
    path = tmp_path / "config" / "presets"
    monkeypatch.setattr(presets, "PRESETS_DIR", path)
    return path
