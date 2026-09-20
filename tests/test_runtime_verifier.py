from pathlib import Path
from installer.runtime_verifier import MSCLoaderLogParser, RuntimeStatus


def test_runtime_verifier_loaded(tmp_path: Path):
    game_dir = tmp_path / "MSC"
    game_dir.mkdir(parents=True)
    log_file = game_dir / "output_log.txt"

    log_content = """
Initialize engine version: 5.0.0f4
[MSCLoader] Initializing MSCLoader v1.2.7...
[MSCLoader] Mod Lights On Switches loaded successfully!
Loaded 1 mods!
"""
    log_file.write_text(log_content)

    parser = MSCLoaderLogParser(game_dir=game_dir)
    result = parser.verify_mod_runtime("Lights On Switches", dll_name="LightsOnSwitches.dll")

    assert result.status == RuntimeStatus.LOADED
    assert "Confirmed loaded" in result.details


def test_runtime_verifier_load_failed(tmp_path: Path):
    game_dir = tmp_path / "MSC"
    game_dir.mkdir(parents=True)
    log_file = game_dir / "output_log.txt"

    log_content = """
[MSCLoader] Error loading Lights On Switches: System.NullReferenceException
"""
    log_file.write_text(log_content)

    parser = MSCLoaderLogParser(game_dir=game_dir)
    result = parser.verify_mod_runtime("Lights On Switches", dll_name="LightsOnSwitches.dll")

    assert result.status == RuntimeStatus.LOAD_FAILED
    assert "Error recorded in log" in result.details


def test_runtime_verifier_unknown_when_not_mentioned(tmp_path: Path):
    game_dir = tmp_path / "MSC"
    game_dir.mkdir(parents=True)
    log_file = game_dir / "output_log.txt"

    log_content = "Game started without mods.\n"
    log_file.write_text(log_content)

    parser = MSCLoaderLogParser(game_dir=game_dir)
    result = parser.verify_mod_runtime("UnrelatedMod")

    assert result.status == RuntimeStatus.UNKNOWN
