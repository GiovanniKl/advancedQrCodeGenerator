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


def imported(result):
    return [new for _old, new in result.imported]


def test_import_legacy_presets(legacy_dir):
    result = presets.import_legacy_presets(legacy_dir)
    assert result.imported == [("old.txt", "old")]
    assert result.failed == []
    assert presets.read_preset("old")["version"] == 2
    assert (legacy_dir / "old.txt").read_text(encoding="utf-8") == LEGACY_TEXT


def test_import_reads_windows_encoded_files(legacy_dir, monkeypatch):
    # the original script saved presets in the system encoding, e.g.
    # cp1250 on Czech Windows; pretend to be such a system
    monkeypatch.setattr(presets.locale, "getencoding", lambda: "cp1250")
    (legacy_dir / "cz.txt").write_bytes(
        "mess=Příliš žluťoučký kůň\nsavedir=C:\\programování\n".encode("cp1250")
    )
    result = presets.import_legacy_presets(legacy_dir)
    assert "cz" in imported(result)
    settings = presets.read_preset("cz")
    assert settings["message"] == "Příliš žluťoučký kůň"
    assert settings["save_dir"] == "C:\\programování"


def test_import_runs_once_per_file(legacy_dir):
    presets.import_legacy_presets(legacy_dir)
    presets.delete_preset("old")
    assert presets.import_legacy_presets(legacy_dir).imported == []
    assert presets.list_presets() == []
    # a file added to the old folder later is still imported
    (legacy_dir / "later.txt").write_text("mess=x\n", encoding="utf-8")
    assert imported(presets.import_legacy_presets(legacy_dir)) == ["later"]


def test_import_numbers_names_that_are_taken(legacy_dir):
    presets.write_preset("old", {"message": "new"})
    presets.write_preset("old 2", {"message": "newer"})
    result = presets.import_legacy_presets(legacy_dir)
    assert result.imported == [("old.txt", "old 3")]
    assert presets.read_preset("old") == {"message": "new"}
    assert presets.read_preset("old 3")["version"] == 2


def test_import_again(legacy_dir):
    presets.import_legacy_presets(legacy_dir)
    assert presets.import_legacy_presets(legacy_dir).imported == []
    result = presets.import_legacy_presets(legacy_dir, again=True)
    assert result.imported == [("old.txt", "old 2")]


@pytest.mark.parametrize("pick", ["presets folder", "app folder"])
def test_find_legacy_folder(legacy_dir, pick):
    chosen = legacy_dir if pick == "presets folder" else legacy_dir.parent
    assert presets.find_legacy_folder(chosen) == legacy_dir


def test_find_legacy_folder_without_presets(tmp_path):
    (tmp_path / "presets").mkdir()
    (tmp_path / "notes.md").write_text("x", encoding="utf-8")
    assert presets.find_legacy_folder(tmp_path) is None


def test_legacy_presets_splits_new_and_imported(legacy_dir):
    presets.import_legacy_presets(legacy_dir)
    (legacy_dir / "later.txt").write_text("mess=x\n", encoding="utf-8")
    new, imported = presets.legacy_presets(legacy_dir)
    assert [path.name for path in new] == ["later.txt"]
    assert [path.name for path in imported] == ["old.txt"]


def test_import_retries_unreadable_files(legacy_dir):
    (legacy_dir / "broken.txt").mkdir()  # reading a folder fails
    result = presets.import_legacy_presets(legacy_dir)
    assert imported(result) == ["old"]
    assert [old for old, _reason in result.failed] == ["broken.txt"]
    (legacy_dir / "broken.txt").rmdir()
    (legacy_dir / "broken.txt").write_text("mess=ok\n", encoding="utf-8")
    assert imported(presets.import_legacy_presets(legacy_dir)) == ["broken"]


def test_import_removes_marker_of_early_versions(legacy_dir, presets_dir):
    # early versions marked whole folders as imported, even when every
    # file failed; their marker must not block the import
    presets_dir.mkdir(parents=True)
    marker = presets_dir / ".imported-legacy-dirs"
    marker.write_text(str(legacy_dir.resolve()) + "\n", encoding="utf-8")
    assert imported(presets.import_legacy_presets(legacy_dir)) == ["old"]
    assert not marker.exists()


def test_import_without_legacy_dir(tmp_path):
    result = presets.import_legacy_presets(tmp_path / "missing")
    assert (result.imported, result.failed) == ([], [])
