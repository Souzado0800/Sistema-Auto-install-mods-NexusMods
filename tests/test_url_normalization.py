"""Tests for URL normalization and input deduplication."""

from browser.manual import parse_urls_from_text
from browser.normalizer import CanonicalModKey, normalize_nexus_url


def test_url_normalization_standard():
    url = "https://www.nexusmods.com/skyrimspecialedition/mods/1234"
    norm = normalize_nexus_url(url)
    assert norm is not None
    assert norm.game_domain == "skyrimspecialedition"
    assert norm.mod_id == 1234
    assert norm.key == CanonicalModKey("skyrimspecialedition", 1234)
    assert norm.canonical_url == "https://www.nexusmods.com/skyrimspecialedition/mods/1234"


def test_url_normalization_with_tabs_and_params():
    url1 = "https://nexusmods.com/skyrimspecialedition/mods/1234?tab=files"
    url2 = "https://www.nexusmods.com/skyrimspecialedition/mods/1234?param=foo&tab=description#main-content"
    url3 = "http://nexusmods.com/skyrimspecialedition/mods/1234/"

    norm1 = normalize_nexus_url(url1)
    norm2 = normalize_nexus_url(url2)
    norm3 = normalize_nexus_url(url3)

    assert norm1 is not None and norm2 is not None and norm3 is not None
    assert norm1.key == norm2.key == norm3.key
    assert norm1.canonical_url == norm2.canonical_url == norm3.canonical_url


def test_url_normalization_nxm_protocol():
    nxm = "nxm://skyrimspecialedition/mods/32444/files/100200?key=abcXYZ123&expires=1700000000&user_id=999"
    norm = normalize_nexus_url(nxm)
    assert norm is not None
    assert norm.game_domain == "skyrimspecialedition"
    assert norm.mod_id == 32444
    assert norm.file_id == 100200
    assert norm.nxm_key == "abcXYZ123"
    assert norm.nxm_expires == 1700000000


def test_parse_and_deduplicate_urls():
    text = """
    # This is a comment
    https://www.nexusmods.com/fallout4/mods/5678
    https://www.nexusmods.com/fallout4/mods/5678?tab=files
    https://www.nexusmods.com/fallout4/mods/5678?something=true

    # Another game
    https://www.nexusmods.com/cyberpunk2077/mods/107
    nxm://cyberpunk2077/mods/107/files/555?key=token123&expires=1800000000

    # Invalid line
    https://google.com/search?q=skyrim
    not a url
    """
    results = parse_urls_from_text(text)
    assert len(results) == 2  # fallout4:5678 and cyberpunk2077:107

    cp_mod = next(m for m in results if m.game_domain == "cyberpunk2077")
    assert cp_mod.mod_id == 107
    # Should prefer the NXM link containing the key token
    assert cp_mod.nxm_key == "token123"
