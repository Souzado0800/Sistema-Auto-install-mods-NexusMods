"""Tests for game directory and MSCLoader auto-detection."""

from core.detector import MSCDetector


def test_msc_detector_preferred_mods_dir(tmp_path):
    mods_dir = tmp_path / "My Summer Car" / "Mods"
    assets_dir = mods_dir / "Assets"
    assets_dir.mkdir(parents=True)

    env = MSCDetector.detect(preferred_mods_dir=mods_dir)
    assert env is not None
    assert env.mods_dir == mods_dir
    assert env.is_mscloader_present is True


def test_msc_detector_game_with_managed_dll(tmp_path, monkeypatch):
    fake_game = tmp_path / "SteamGames" / "My Summer Car"
    managed_dir = fake_game / "mysummercar_Data" / "Managed"
    managed_dir.mkdir(parents=True)
    (managed_dir / "MSCLoader.dll").write_bytes(b"LOADER_BINARY")

    mods_dir = fake_game / "Mods"
    mods_dir.mkdir()

    monkeypatch.setattr("core.detector.KNOWN_GAME_CANDIDATES", [fake_game])

    env = MSCDetector.detect()
    assert env is not None
    assert env.game_dir == fake_game
    assert env.mods_dir == mods_dir
    assert env.is_mscloader_present is True
