"""Tests of reading and writing preset files."""

import pytest

from aqrgen import presets


@pytest.fixture(autouse=True)
def presets_dir(tmp_path, monkeypatch):
    path = tmp_path / "presets"
    monkeypatch.setattr(presets, "PRESETS_DIR", path)
    return path


def test_list_creates_missing_dir(presets_dir):
    assert not presets_dir.exists()
    assert presets.list_presets() == []
    assert presets_dir.is_dir()


def test_round_trip():
    values = {"mess": "https://example.com/?a=b&c=d", "size": 3, "embim": True}
    presets.write_preset("p", values)
    assert presets.read_preset("p") == {
        "mess": "https://example.com/?a=b&c=d",
        "size": "3",
        "embim": "True",
    }


def test_list_is_sorted():
    for name in ("b", "a", "c"):
        presets.write_preset(name, {})
    assert presets.list_presets() == ["a", "b", "c"]


def test_delete():
    presets.write_preset("p", {})
    presets.delete_preset("p")
    assert presets.list_presets() == []


def test_missing_preset_raises():
    with pytest.raises(FileNotFoundError):
        presets.read_preset("missing")
    with pytest.raises(FileNotFoundError):
        presets.delete_preset("missing")


def test_reads_legacy_file(presets_dir):
    # file written by the original single-script version
    presets_dir.mkdir()
    (presets_dir / "old.txt").write_text(
        "mess=hi\nsavedir=\nsize=2\nembim=False\nbgcolor=(255, 255, 255)\n",
        encoding="utf-8",
    )
    assert presets.read_preset("old") == {
        "mess": "hi",
        "savedir": "",
        "size": "2",
        "embim": "False",
        "bgcolor": "(255, 255, 255)",
    }
