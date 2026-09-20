import struct
from browser.session_reader import ChromiumSessionReader, TabOrigin


def test_snss_open_and_closed_tabs():
    # Build synthetic SNSS binary data
    # SNSS Header: 4 bytes magic 'SNSS', 4 bytes version (3)
    header = b"SNSS\x03\x00\x00\x00"

    # Command 0: SetTabWindow tab_id=1, win_id=10
    cmd0_payload = struct.pack("<ii", 1, 10)
    cmd0 = struct.pack("<HB", 1 + len(cmd0_payload), 0) + cmd0_payload

    # Command 6: UpdateTabNavigation tab_id=1, url="https://www.nexusmods.com/mysummercar/mods/868"
    nav_url = b"https://www.nexusmods.com/mysummercar/mods/868"
    cmd6_payload = struct.pack("<i", 1) + b"\x00" * 4 + nav_url
    cmd6 = struct.pack("<HB", 1 + len(cmd6_payload), 6) + cmd6_payload

    # Tab 2: SetTabWindow tab_id=2, win_id=10
    cmd0_tab2_payload = struct.pack("<ii", 2, 10)
    cmd0_tab2 = struct.pack("<HB", 1 + len(cmd0_tab2_payload), 0) + cmd0_tab2_payload

    # Tab 2 nav: "https://www.nexusmods.com/mysummercar/mods/3518"
    nav_url2 = b"https://www.nexusmods.com/mysummercar/mods/3518"
    cmd6_tab2_payload = struct.pack("<i", 2) + b"\x00" * 4 + nav_url2
    cmd6_tab2 = struct.pack("<HB", 1 + len(cmd6_tab2_payload), 6) + cmd6_tab2_payload

    # Command 3: TabClosed tab_id=2
    cmd3_tab2_payload = struct.pack("<i", 2)
    cmd3_tab2 = struct.pack("<HB", 1 + len(cmd3_tab2_payload), 3) + cmd3_tab2_payload

    data = header + cmd0 + cmd6 + cmd0_tab2 + cmd6_tab2 + cmd3_tab2

    open_tabs = ChromiumSessionReader.parse_snss_open_tabs(data)

    assert 1 in open_tabs, "Tab 1 should still be open"
    assert "868" in open_tabs[1]

    assert 2 not in open_tabs, "Tab 2 should be closed"
    assert TabOrigin.ACTIVE_SESSION.value == "ACTIVE_SESSION"
