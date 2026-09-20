"""Installation manager coordinating mod extraction, manifest recording, and repair."""

import shutil
import zipfile
from pathlib import Path
from typing import Any

from database.repositories import InstallationRepository
from dependencies.models import DependencyNode
from utils.hashing import compute_file_hash
from utils.logging import get_logger

from .backup import BackupManager
from .extractor import ExtractionResult, SafeArchiveExtractor
from .mscloader import MSCLoaderInspector
from .profiles import GameProfile, ProfileManager
from .safety import SafeArchiveGuard
from .staging import StagingWorkspace

logger = get_logger("nexus.installer.manager")


class InstallationManager:
    """Manages mod installations, manifests, updates, and integrity repairs."""

    def __init__(
        self,
        installation_repo: InstallationRepository,
        profile_manager: ProfileManager | None = None,
        backup_manager: BackupManager | None = None,
        staging_workspace: StagingWorkspace | None = None,
    ):
        self.repo = installation_repo
        self.profiles = profile_manager or ProfileManager()
        self.backup_mgr = backup_manager or BackupManager()
        self.staging = staging_workspace or StagingWorkspace()
        self.extractor = SafeArchiveExtractor(backup_manager=self.backup_mgr)

    def install_mod(
        self,
        item: DependencyNode,
        archive_path: Path,
        game_root_dir: Path,
    ) -> ExtractionResult:
        """Extract and install mod archive using profile-specific strategy (MSCLoader / Generic)."""
        profile: GameProfile = self.profiles.get_profile(item.game_domain)

        # Determine target directory
        if profile.mods_directory.startswith("/"):
            dest_dir = Path(profile.mods_directory)
        elif profile.mods_directory:
            dest_dir = game_root_dir / profile.mods_directory
        else:
            dest_dir = game_root_dir

        dest_dir.mkdir(parents=True, exist_ok=True)

        if profile.install_strategy == "mscloader":
            return self._install_mscloader_mod(item, archive_path, dest_dir, profile.game)
        else:
            return self._install_generic_mod(item, archive_path, dest_dir, profile.game)

    def _install_mscloader_mod(
        self,
        item: DependencyNode,
        archive_path: Path,
        dest_dir: Path,
        profile_name: str,
    ) -> ExtractionResult:
        """Smart MSCLoader mod installation with structure inspection and staging."""
        plan = MSCLoaderInspector.inspect_archive(archive_path, item.name)

        if plan.requires_manual:
            reasons = "; ".join(f"{f}: {r}" for f, r in plan.unsupported_files)
            msg = f"MANUAL INSTALLATION REQUIRED for '{item.name}': {reasons}"
            logger.warning(msg)
            return ExtractionResult(success=False, error_message=msg)

        logger.info(f"MSCLoader Plan for '{item.name}': {len(plan.file_mappings)} file(s) mapped to {dest_dir}")

        # Transactional staging
        stage_dir = self.staging.create_session(item.name)
        manifest: list[dict[str, Any]] = []

        try:
            with zipfile.ZipFile(archive_path, "r") as zf:
                # 1. Extract mapped files into staging first
                for src_member, rel_dest in plan.file_mappings:
                    staged_target = SafeArchiveGuard.validate_destination_path(stage_dir, rel_dest)
                    staged_target.parent.mkdir(parents=True, exist_ok=True)

                    with zf.open(src_member) as src, open(staged_target, "wb") as dst:
                        while chunk := src.read(64 * 1024):
                            dst.write(chunk)

            # 2. Conflict detection & Deployment to live Mods directory
            for _, rel_dest in plan.file_mappings:
                staged_file = stage_dir / rel_dest
                final_target = dest_dir / rel_dest
                final_target.parent.mkdir(parents=True, exist_ok=True)

                staged_sha256 = compute_file_hash(staged_file, "sha256")

                # Check if file already exists in Mods/
                if final_target.is_file():
                    existing_sha256 = compute_file_hash(final_target, "sha256")
                    if staged_sha256.lower() == existing_sha256.lower():
                        logger.info(f"Shared file identical: {rel_dest} (reused safely)")
                    else:
                        logger.warning(f"File conflict detected for {rel_dest}! Creating backup before overwrite.")
                        self.backup_mgr.backup_if_exists(final_target, dest_dir)
                else:
                    self.backup_mgr.backup_if_exists(final_target, dest_dir)

                # Move staged file to final destination
                shutil.copy2(staged_file, final_target)

                manifest.append({
                    "relative_path": rel_dest,
                    "file_size": final_target.stat().st_size,
                    "sha256": staged_sha256,
                })

            # Record in SQLite database
            self.repo.record_installation(
                game_domain=item.game_domain,
                mod_id=item.mod_id,
                file_id=item.file_id or 0,
                mod_name=item.name,
                version=item.version or "1.0",
                profile=profile_name,
                install_dir=str(dest_dir),
                manifest=manifest,
            )

            self.staging.cleanup()
            logger.info(f"Successfully installed MSCLoader mod: {item.name} ({len(manifest)} files)")
            return ExtractionResult(
                success=True,
                extracted_count=len(manifest),
                manifest=manifest,
            )

        except Exception as e:
            logger.error(f"Error during MSCLoader installation for {item.name}: {e}")
            self.backup_mgr.rollback()
            self.staging.cleanup()
            return ExtractionResult(success=False, error_message=str(e))

    def _install_generic_mod(
        self,
        item: DependencyNode,
        archive_path: Path,
        dest_dir: Path,
        profile_name: str,
    ) -> ExtractionResult:
        """Standard extraction for generic profiles."""
        logger.info(f"Installing {item.name} into {dest_dir} using profile '{profile_name}'...")
        result = self.extractor.extract(archive_path, dest_dir)

        if result.success:
            self.repo.record_installation(
                game_domain=item.game_domain,
                mod_id=item.mod_id,
                file_id=item.file_id or 0,
                mod_name=item.name,
                version=item.version or "1.0",
                profile=profile_name,
                install_dir=str(dest_dir),
                manifest=result.manifest,
            )
            logger.info(f"Installed {item.name}: {result.extracted_count} files recorded in manifest.")
        else:
            logger.error(f"Installation failed for {item.name}: {result.error_message}")

        return result

    def repair_mod(self, game_domain: str, mod_id: int, game_root_dir: Path) -> dict[str, Any]:
        """Verify every file recorded in the mod's manifest against disk."""
        installation = self.repo.get_installation(game_domain, mod_id)
        if not installation:
            return {"status": "not_installed", "error": f"Mod {game_domain}:{mod_id} is not recorded as installed"}

        install_dir = Path(installation["install_dir"])
        manifest = self.repo.get_manifest(game_domain, mod_id)

        valid_files: list[str] = []
        missing_files: list[str] = []
        modified_files: list[str] = []

        for f in manifest:
            rel = f["relative_path"]
            disk_path = install_dir / rel

            if not disk_path.is_file():
                missing_files.append(rel)
                continue

            if disk_path.stat().st_size != f["file_size"]:
                modified_files.append(rel)
                continue

            current_sha = compute_file_hash(disk_path, "sha256")
            if current_sha.lower() != f["sha256"].lower():
                modified_files.append(rel)
            else:
                valid_files.append(rel)

        is_healthy = len(missing_files) == 0 and len(modified_files) == 0
        return {
            "status": "healthy" if is_healthy else "corrupted",
            "mod_name": installation["mod_name"],
            "version": installation["version"],
            "total_files": len(manifest),
            "valid_count": len(valid_files),
            "missing": missing_files,
            "modified": modified_files,
        }

    def check_for_updates(
        self,
        game_domain: str,
        mod_id: int,
        latest_file_id: int,
        latest_version: str | None = None,
    ) -> dict[str, Any]:
        """Compare installed version/file with latest available version."""
        inst = self.repo.get_installation(game_domain, mod_id)
        if not inst:
            return {"status": "not_installed"}

        installed_file_id = inst["file_id"]
        installed_version = inst["version"]

        has_update = latest_file_id > installed_file_id or (
            latest_version and latest_version != installed_version
        )

        return {
            "status": "update_available" if has_update else "up_to_date",
            "mod_name": inst["mod_name"],
            "installed_version": installed_version,
            "available_version": latest_version or "latest",
            "installed_file_id": installed_file_id,
            "available_file_id": latest_file_id,
        }
