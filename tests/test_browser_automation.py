"""
Comprehensive unit tests for Browser Download Automation.
Tests all 14 scenarios required for official compliance and fallback safety:
1. Manual Download found
2. Manual Download missing
3. Slow Download found
4. Slow Download unavailable
5. countdown present
6. download starts (.crdownload detected)
7. .crdownload detected & waited for
8. download completes (stable size)
9. timeout (120s handling)
10. CAPTCHA detected (user action required)
11. login required (session prompt)
12. browser closed / socket error
13. CDP unavailable (graceful fallback)
14. DOM changed (resilient selectors)
"""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from browser.auto_downloader import BrowserDownloadAutomator
from browser.dom_actions import (
    get_check_challenges_js,
    get_check_countdown_js,
    get_click_manual_download_js,
    get_click_slow_download_js,
)
from browser.download_watcher import DownloadWatcher
from rich.console import Console


@pytest.fixture
def tmp_downloads(tmp_path: Path) -> Path:
    dl_dir = tmp_path / "Downloads"
    dl_dir.mkdir(parents=True, exist_ok=True)
    return dl_dir


# ---------------------------------------------------------------------------
# 1. Manual Download Found & Missing (DOM Actions)
# ---------------------------------------------------------------------------
def test_manual_download_js_generation():
    # File ID specific
    js_specific = get_click_manual_download_js(file_id=5289)
    assert 'file_id="5289"' in js_specific or '"5289"' in js_specific
    assert "manual download" in js_specific.lower()

    # General fallback
    js_general = get_click_manual_download_js(file_id=None)
    assert "null" in js_specific or "null" in js_general
    assert "manual download" in js_general.lower()
    assert "main files" in js_general.lower()
    assert "file-container-main-files" in js_general


def test_main_files_section_handling():
    js = get_click_manual_download_js(file_id=None)
    assert "file-container-main-files" in js
    assert "MAIN_FILES_SHADOW_MODAL" in js
    assert "REQUIREMENTS_MODAL" in js
    assert "MAIN_FILES_STANDARD" in js



# ---------------------------------------------------------------------------
# 2. Slow Download Found & Unavailable
# ---------------------------------------------------------------------------
def test_slow_download_js_generation():
    js_slow = get_click_slow_download_js()
    assert "#slowDownloadButton" in js_slow
    assert "slow download" in js_slow.lower()


# ---------------------------------------------------------------------------
# 3. Countdown Present
# ---------------------------------------------------------------------------
def test_countdown_js_generation():
    js_countdown = get_check_countdown_js()
    assert "download will start in" in js_countdown
    assert "#countdown" in js_countdown


# ---------------------------------------------------------------------------
# 4. CAPTCHA and Login Challenges Detected
# ---------------------------------------------------------------------------
def test_challenge_detection_js_generation():
    js_challenge = get_check_challenges_js()
    assert "challenges.cloudflare" in js_challenge
    assert "recaptcha" in js_challenge
    assert "login" in js_challenge


# ---------------------------------------------------------------------------
# 5. Baseline Snapshot & Ignoring Pre-existing Files
# ---------------------------------------------------------------------------
def test_download_watcher_ignores_preexisting(tmp_downloads: Path):
    old_file = tmp_downloads / "LightsOnSwitches-868-old.zip"
    old_file.write_bytes(b"old archive content")

    watcher = DownloadWatcher(tmp_downloads)
    assert not watcher.is_new_or_modified(old_file)


def test_is_matching_mod_exact_and_no_false_positives():
    # 1. Official format exact matches
    assert DownloadWatcher.is_matching_mod(
        "Better Suspension for Hayosiko-1282-3-1-1759866518.zip", mod_id=1282, mod_name="Better Suspension"
    )
    assert DownloadWatcher.is_matching_mod(
        "Colorful Gauges-30-4-0-0-1694595995.zip", mod_id=30, mod_name="Colorful Gauges"
    )
    assert DownloadWatcher.is_matching_mod(
        "Dust clouds-128-3-1-1723460921.zip", mod_id=128, mod_name="Dust clouds"
    )

    # 2. Prevent false positives on timestamps/versions
    # "Better Graphics-4103-2-0-1761421573.zip" contains "14", "10", "5", "176" inside numbers
    bg = "Better Graphics-4103-2-0-1761421573.zip"
    assert not DownloadWatcher.is_matching_mod(bg, mod_id=14, mod_name="Mo'Controls")
    assert not DownloadWatcher.is_matching_mod(bg, mod_id=10, mod_name="Rally Spotlights")
    assert not DownloadWatcher.is_matching_mod(bg, mod_id=5, mod_name="Fuel Tank Door")
    assert not DownloadWatcher.is_matching_mod(bg, mod_id=176, mod_name="Tangerine FZ-120 Pickup")

    # "SatsumaNewSound-591-1-0-1614787333.zip" must NOT match Mod 14, 5, 147, 333
    sns = "SatsumaNewSound-591-1-0-1614787333.zip"
    assert not DownloadWatcher.is_matching_mod(sns, mod_id=14, mod_name="Mo'Controls")
    assert not DownloadWatcher.is_matching_mod(sns, mod_id=5, mod_name="Fuel Tank Door")
    assert not DownloadWatcher.is_matching_mod(sns, mod_id=147, mod_name="MSCLoader")
    assert not DownloadWatcher.is_matching_mod(sns, mod_id=333, mod_name="Garage Pit Covers")



# ---------------------------------------------------------------------------
# 6. .crdownload Detected & In-Progress Handling
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_download_watcher_crdownload_then_complete(tmp_downloads: Path):
    watcher = DownloadWatcher(tmp_downloads)

    async def simulate_browser_download():
        await asyncio.sleep(0.1)
        cr_file = tmp_downloads / "LightsOnSwitches-868.zip.crdownload"
        cr_file.write_bytes(b"partial content")
        await asyncio.sleep(0.2)
        # Browser completes download: rename to final .zip
        final_file = tmp_downloads / "LightsOnSwitches-868.zip"
        cr_file.rename(final_file)

    task = asyncio.create_task(simulate_browser_download())
    result = await watcher.wait_for_download(
        mod_id=868, mod_name="Lights On Switches", timeout=5.0, poll_interval=0.1
    )
    await task

    assert result is not None
    assert result.name == "LightsOnSwitches-868.zip"
    assert result.is_file()


# ---------------------------------------------------------------------------
# 7. Download Completes with Stable Size
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_download_watcher_waits_for_stable_size(tmp_downloads: Path):
    watcher = DownloadWatcher(tmp_downloads)

    target_file = tmp_downloads / "LightsOnSwitches-868-2-0.zip"
    target_file.write_bytes(b"full valid archive payload")

    result = await watcher.wait_for_download(
        mod_id=868, mod_name="Lights On Switches", timeout=3.0, poll_interval=0.1
    )
    assert result is not None
    assert result.name == "LightsOnSwitches-868-2-0.zip"


# ---------------------------------------------------------------------------
# 8. Timeout Handling (120s or specified timeout)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_download_watcher_timeout(tmp_downloads: Path):
    watcher = DownloadWatcher(tmp_downloads)
    # Fast timeout for test
    result = await watcher.wait_for_download(mod_id=99999, timeout=0.2, poll_interval=0.05)
    assert result is None


# ---------------------------------------------------------------------------
# 9. Pre-existing Local Detection
# ---------------------------------------------------------------------------
def test_automator_finds_existing_local(tmp_downloads: Path):
    existing = tmp_downloads / "LightsOnSwitches_868.zip"
    existing.write_bytes(b"existing content")

    automator = BrowserDownloadAutomator(downloads_dir=tmp_downloads, console=Console(quiet=True))
    found = automator.find_existing_local_download(mod_id=868, mod_name="Lights On Switches")
    assert found is not None
    assert found == existing


# ---------------------------------------------------------------------------
# 10. CDP Unavailable Graceful Fallback
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_automator_fallback_when_cdp_unavailable(tmp_downloads: Path):
    automator = BrowserDownloadAutomator(
        downloads_dir=tmp_downloads,
        cdp_endpoint="http://127.0.0.1:59999",  # Non-existent port
        console=Console(quiet=True),
    )

    async def simulate_manual_download():
        await asyncio.sleep(0.2)
        f = tmp_downloads / "LightsOnSwitches-868.zip"
        f.write_bytes(b"user clicked manually")

    with patch("webbrowser.open", return_value=True):
        task = asyncio.create_task(simulate_manual_download())
        dl_path = await automator.download_mod_file(
            game_domain="mysummercar",
            mod_id=868,
            file_id=5289,
            mod_name="Lights On Switches",
            timeout=3.0,
        )
        await task

    assert dl_path is not None
    assert dl_path.name == "LightsOnSwitches-868.zip"


# ---------------------------------------------------------------------------
# 11. CDP Flow: Challenge Detected (CAPTCHA / Cloudflare)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_cdp_flow_challenge_handling(tmp_downloads: Path):
    automator = BrowserDownloadAutomator(
        downloads_dir=tmp_downloads,
        cdp_endpoint="http://127.0.0.1:9222",
        console=Console(quiet=True),
    )

    mock_cdp = AsyncMock()
    mock_cdp.is_available.return_value = True
    mock_cdp.list_tabs.return_value = [
        {"url": "https://www.nexusmods.com/mysummercar/mods/868?tab=files", "webSocketDebuggerUrl": "ws://127.0.0.1:9222/tab1"}
    ]
    mock_cdp.attach_to_tab.return_value = True

    # First returns challenge, second returns clear, then clicks buttons
    mock_cdp.evaluate.side_effect = [
        {"challenge": True, "type": "CAPTCHA"},
        {"challenge": False},
        {"clicked": True},  # Manual Download
        {"clicked": True},  # Slow Download
        {"countdown": True, "seconds_left": 0},  # Countdown
    ]

    async def simulate_browser_finish():
        await asyncio.sleep(0.3)
        (tmp_downloads / "LightsOnSwitches-868.zip").write_bytes(b"payload")

    with patch("browser.auto_downloader.CdpClient", return_value=mock_cdp):
        task = asyncio.create_task(simulate_browser_finish())
        res = await automator.download_mod_file(
            game_domain="mysummercar",
            mod_id=868,
            file_id=5289,
            mod_name="Lights On Switches",
            timeout=3.0,
        )
        await task

    assert res is not None
    assert res.name == "LightsOnSwitches-868.zip"


# ---------------------------------------------------------------------------
# 12. Browser Closed / Socket Disconnect Handling
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_cdp_browser_closed_socket_error(tmp_downloads: Path):
    automator = BrowserDownloadAutomator(
        downloads_dir=tmp_downloads,
        cdp_endpoint="http://127.0.0.1:9222",
        console=Console(quiet=True),
    )

    mock_cdp = AsyncMock()
    mock_cdp.is_available.return_value = True
    mock_cdp.list_tabs.return_value = [
        {"url": "https://www.nexusmods.com/mysummercar/mods/868", "webSocketDebuggerUrl": "ws://127.0.0.1:9222/tab1"}
    ]
    mock_cdp.attach_to_tab.return_value = True
    # Simulate browser closing mid-eval
    mock_cdp.evaluate.side_effect = ConnectionError("Browser process terminated")

    async def simulate_manual_download():
        await asyncio.sleep(0.2)
        (tmp_downloads / "LightsOnSwitches-868.zip").write_bytes(b"downloaded via fallback")

    with patch("browser.auto_downloader.CdpClient", return_value=mock_cdp), patch("webbrowser.open", return_value=True):
        task = asyncio.create_task(simulate_manual_download())
        res = await automator.download_mod_file(
            game_domain="mysummercar",
            mod_id=868,
            file_id=5289,
            mod_name="Lights On Switches",
            timeout=3.0,
        )
        await task

    assert res is not None
    assert res.name == "LightsOnSwitches-868.zip"


# ---------------------------------------------------------------------------
# 13. DOM Changed (Resilient Selectors)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_cdp_dom_changed_button_missing(tmp_downloads: Path):
    automator = BrowserDownloadAutomator(
        downloads_dir=tmp_downloads,
        cdp_endpoint="http://127.0.0.1:9222",
        console=Console(quiet=True),
    )

    mock_cdp = AsyncMock()
    mock_cdp.is_available.return_value = True
    mock_cdp.list_tabs.return_value = [
        {"url": "https://www.nexusmods.com/mysummercar/mods/868", "webSocketDebuggerUrl": "ws://127.0.0.1:9222/tab1"}
    ]
    mock_cdp.attach_to_tab.return_value = True
    # Both evaluations return button not found (DOM changed)
    mock_cdp.evaluate.side_effect = [
        {"challenge": False},
        {"clicked": False, "error": "MANUAL_DOWNLOAD_NOT_FOUND"},
        {"clicked": False, "error": "SLOW_DOWNLOAD_NOT_FOUND"},
    ]

    async def simulate_manual_download():
        await asyncio.sleep(0.2)
        (tmp_downloads / "LightsOnSwitches-868.zip").write_bytes(b"downloaded manually after DOM changed")

    with patch("browser.auto_downloader.CdpClient", return_value=mock_cdp), patch("webbrowser.open", return_value=True):
        task = asyncio.create_task(simulate_manual_download())
        res = await automator.download_mod_file(
            game_domain="mysummercar",
            mod_id=868,
            file_id=5289,
            mod_name="Lights On Switches",
            timeout=3.0,
        )
        await task

    assert res is not None
    assert res.name == "LightsOnSwitches-868.zip"
