"""Tests for read-only Chromium/Brave session tab parser."""

from browser.session_reader import ChromiumSessionReader


def test_session_reader_parses_binary_session_file(tmp_path):
    browser_dir = tmp_path / "Brave-Browser"
    profile_dir = browser_dir / "Default"
    sessions_dir = profile_dir / "Sessions"
    sessions_dir.mkdir(parents=True)

    # Simulated binary session file with multiple URLs
    fake_session_data = (
        b"\x00\x14\x06\x00https://www.google.com/search?q=test\x00"
        b"\x00\x28\x06\x00https://www.nexusmods.com/mysummercar/mods/147?tab=files\x00"
        b"\x00\x28\x06\x00https://www.nexusmods.com/mysummercar/mods/147\x00"  # duplicate mod 147
        b"\x00\x28\x06\x00https://www.nexusmods.com/mysummercar/mods/26\x00"
        b"\x00\x28\x06\x00https://www.nexusmods.com/skyrimspecialedition/mods/999\x00"  # different game
        b"\x00\x14\x06\x00https://www.youtube.com/watch?v=123\x00"
    )

    session_file = sessions_dir / "Session_13300000000000000"
    session_file.write_bytes(fake_session_data)

    report = ChromiumSessionReader.extract_nexus_tabs(
        target_game="mysummercar",
        custom_browser_dir=browser_dir,
    )

    assert report is not None
    assert report.total_nexus_urls == 4  # 3 mysummercar + 1 skyrim
    assert len(report.unique_mods) == 2  # mod 147 and mod 26
    mod_ids = {m.mod_id for m in report.unique_mods}
    assert mod_ids == {147, 26}
    assert all(m.game_domain == "mysummercar" for m in report.unique_mods)
