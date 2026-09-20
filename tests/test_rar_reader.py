import subprocess
from core.readers import RarReader


def test_rar_reader_with_7z_tool(tmp_path):
    """
    Validates that RarReader properly invokes 7z to list members and extract bytes.
    Creates a test archive using 7z, then reads members and bytes through RarReader.
    """
    test_dir = tmp_path / "files"
    test_dir.mkdir()
    (test_dir / "LightsOnSwitches.dll").write_bytes(b"LIGHTS_DLL_CONTENT")
    (test_dir / "readme.txt").write_bytes(b"Documentation")

    # Create archive using 7z (7z can create .7z or .zip, but 7z l -slt syntax is identical)
    archive_7z = tmp_path / "test_mod.7z"
    cmd = ["7z", "a", str(archive_7z), str(test_dir / "*")]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0

    # Test RarReader parsing logic on 7z output format
    reader = RarReader(archive_7z)
    members = reader.get_members()

    member_names = [m.filename for m in members]
    assert any("LightsOnSwitches.dll" in name for name in member_names)
    assert any("readme.txt" in name for name in member_names)

    # Extract member bytes
    dll_member = [name for name in member_names if "LightsOnSwitches.dll" in name][0]
    data = reader.read_bytes(dll_member)
    assert data == b"LIGHTS_DLL_CONTENT"
