"""Tests of reading and writing preset files."""

import json
from pathlib import Path

import pytest

from aqrgen import presets

LEGACY_TEXT = (
    "mess=https://example.com/?a=b\n"
    "savedir=\n"
    "size=2\n"
    "embim=False\n"
    "bdsize=oops\n"
    "bgcolor=(255, 255, 255)\n"
    "unknown=1\n"
)


@pytest.fixture
def legacy_dir(tmp_path):
    path = tmp_path / "old" / "presets"
    path.mkdir(parents=True)
    (path / "old.txt").write_text(LEGACY_TEXT, encoding="utf-8")
    return path


# --- location --------------------------------------------------------


@pytest.mark.parametrize(
    ("platform", "env", "expected"),
    [
        ("win32", {"APPDATA": "C:/AppData"}, "C:/AppData/aqrgen/presets"),
        ("linux", {"XDG_CONFIG_HOME": "/cfg"}, "/cfg/aqrgen/presets"),
        ("linux", {}, "~/.config/aqrgen/presets"),
        ("darwin", {}, "~/Library/Application Support/aqrgen/presets"),
    ],
)
def test_default_presets_dir(monkeypatch, platform, env, expected):
    monkeypatch.setattr(presets.sys, "platform", platform)
    for key in ("APPDATA", "XDG_CONFIG_HOME"):
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    assert presets.default_presets_dir() == Path(expected).expanduser()


def test_list_creates_missing_dir(presets_dir):
    assert not presets_dir.exists()
    assert presets.list_presets() == []
    assert presets_dir.is_dir()


# --- JSON presets ----------------------------------------------------


def test_round_trip_keeps_types(presets_dir):
    settings = {"message": "Ünïcode ✓", "version": 3, "embed_image": True}
    presets.write_preset("p", settings)
    assert presets.read_preset("p") == settings
    data = json.loads((presets_dir / "p.json").read_text(encoding="utf-8"))
    assert data["format_version"] == presets.FORMAT_VERSION


def test_list_is_sorted_ignoring_case():
    for name in ("b", "A", "c"):
        presets.write_preset(name, {})
    assert presets.list_presets() == ["A", "b", "c"]


def test_delete():
    presets.write_preset("p", {})
    presets.delete_preset("p")
    assert presets.list_presets() == []


def test_missing_preset_raises():
    with pytest.raises(FileNotFoundError):
        presets.read_preset("missing")
    with pytest.raises(FileNotFoundError):
        presets.delete_preset("missing")


@pytest.mark.parametrize("name", ["", "  ", "a/b", "..", ".hidden", "a:b"])
def test_invalid_names_raise(name):
    with pytest.raises(ValueError, match="preset name|Preset name"):
        presets.write_preset(name, {})


@pytest.mark.parametrize(
    ("content", "message"),
    [("{not json", "not valid JSON"), ('{"a": 1}', "not an aqrgen preset")],
)
def test_broken_file_raises(presets_dir, content, message):
    presets_dir.mkdir(parents=True)
    (presets_dir / "bad.json").write_text(content, encoding="utf-8")
    with pytest.raises(ValueError, match=message):
        presets.read_preset("bad")


# --- old .txt presets ------------------------------------------------


def test_read_legacy_preset(legacy_dir):
    assert presets.read_legacy_preset(legacy_dir / "old.txt") == {
        "message": "https://example.com/?a=b",
        "save_dir": "",
        "version": 2,
        "embed_image": False,
        "border": "oops",  # kept as text, the GUI reports it on load
        "back_color": "(255, 255, 255)",
    }


def test_import_legacy_presets(legacy_dir):
    assert presets.import_legacy_presets(legacy_dir) == ["old"]
    assert presets.read_preset("old")["version"] == 2
    assert (legacy_dir / "old.txt").read_text(encoding="utf-8") == LEGACY_TEXT


def test_import_runs_once_per_folder(legacy_dir):
    presets.import_legacy_presets(legacy_dir)
    presets.delete_preset("old")
    assert presets.import_legacy_presets(legacy_dir) == []
    assert presets.list_presets() == []


def test_import_keeps_existing_json(legacy_dir):
    presets.write_preset("old", {"message": "new"})
    assert presets.import_legacy_presets(legacy_dir) == []
    assert presets.read_preset("old") == {"message": "new"}


def test_import_without_legacy_dir(tmp_path):
    assert presets.import_legacy_presets(tmp_path / "missing") == []
