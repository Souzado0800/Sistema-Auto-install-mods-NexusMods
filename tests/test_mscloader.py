"""Tests for smart MSCLoader archive structure inspection and planning."""

import io
import zipfile
from pathlib import Path

from installer.mscloader import MSCLoaderInspector


def test_mscloader_root_dll(temp_dir: Path):
    """Archive with MyMod.dll and README.txt at root."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("MyCoolMod.dll", "DLL_BINARY_CONTENT")
        zf.writestr("README.txt", "How to install")
        zf.writestr("CHANGELOG.md", "Version 1.0")
    archive = temp_dir / "my_cool_mod.zip"
    archive.write_bytes(buf.getvalue())

    plan = MSCLoaderInspector.inspect_archive(archive, "MyCoolMod")
    assert plan.is_automatic
    assert not plan.requires_manual
    assert plan.dll_count == 1

    # Mappings should contain MyCoolMod.dll -> MyCoolMod.dll, ignoring README and CHANGELOG
    dest_files = [dest for _, dest in plan.file_mappings]
    assert dest_files == ["MyCoolMod.dll"]


def test_mscloader_mods_wrapper_folder(temp_dir: Path):
    """Archive wrapped in Mods/ folder (Mods/MyMod.dll and Mods/Assets/MyMod/texture.png)."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("Mods/AdvancedTelemetry.dll", "DLL_BINARY")
        zf.writestr("Mods/Assets/AdvancedTelemetry/gauge.png", "PNG_DATA")
    archive = temp_dir / "telemetry.zip"
    archive.write_bytes(buf.getvalue())

    plan = MSCLoaderInspector.inspect_archive(archive, "AdvancedTelemetry")
    assert plan.is_automatic
    assert not plan.requires_manual
    assert plan.dll_count == 1

    # Outer 'Mods/' must be stripped!
    mapping_dict = dict(plan.file_mappings)
    assert mapping_dict["Mods/AdvancedTelemetry.dll"] == "AdvancedTelemetry.dll"
    assert mapping_dict["Mods/Assets/AdvancedTelemetry/gauge.png"] == "Assets/AdvancedTelemetry/gauge.png"


def test_mscloader_modname_wrapper_folder(temp_dir: Path):
    """Archive wrapped in ModName/ folder (e.g. BetterSuspension/BetterSuspension.dll)."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("BetterSuspension/BetterSuspension.dll", "DLL_BINARY")
        zf.writestr("BetterSuspension/Assets/BetterSuspension/spring.unity3d", "UNITY3D_DATA")
        zf.writestr("BetterSuspension/Config/settings.xml", "<config/>")
    archive = temp_dir / "better_suspension.zip"
    archive.write_bytes(buf.getvalue())

    plan = MSCLoaderInspector.inspect_archive(archive, "BetterSuspension")
    assert plan.is_automatic
    assert not plan.requires_manual
    assert plan.dll_count == 1

    mapping_dict = dict(plan.file_mappings)
    assert mapping_dict["BetterSuspension/BetterSuspension.dll"] == "BetterSuspension.dll"
    assert mapping_dict["BetterSuspension/Assets/BetterSuspension/spring.unity3d"] == "Assets/BetterSuspension/spring.unity3d"
    assert mapping_dict["BetterSuspension/Config/settings.xml"] == "Config/settings.xml"


def test_mscloader_non_standard_requires_manual(temp_dir: Path):
    """Archive targeting game root mysummercar_Data or containing executable patcher."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("mysummercar_Data/Managed/Assembly-CSharp.dll", "CORE_GAME_OVERWRITE")
        zf.writestr("installer.exe", "PATCHER_EXE")
    archive = temp_dir / "invasive_mod.zip"
    archive.write_bytes(buf.getvalue())

    plan = MSCLoaderInspector.inspect_archive(archive, "InvasiveMod")
    assert not plan.is_automatic
    assert plan.requires_manual
    assert len(plan.unsupported_files) >= 2
