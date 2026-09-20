"""
Backup and transactional rollback manager for MSCLoader mods.
Preserves existing files in mods_dir / "_Backups" matching AutoInstallModMySummerCar convention.
"""

from datetime import datetime
from pathlib import Path
import shutil

from utils.logging import get_logger

logger = get_logger("core.backups")


class MSCBackupManager:
    def __init__(self, mods_dir: Path | str):
        self.mods_dir = Path(mods_dir).resolve()
        self.backup_dir = self.mods_dir / "_Backups"

    def create_backup(self, target_file: Path | str) -> Path | None:
        p = Path(target_file).resolve()
        if not p.is_file():
            return None

        try:
            self.backup_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            backup_name = f"{p.name}_{timestamp}.bak"
            backup_path = self.backup_dir / backup_name
            shutil.copy2(p, backup_path)
            logger.info(f"Backup de segurança criado: _Backups/{backup_name}")
            return backup_path
        except Exception as e:
            logger.error(f"Falha ao criar backup de {p}: {e}")
            return None

    def rollback(self, written_files: list[Path], created_backups: dict[Path, Path]):
        """
        Reverts partial installation:
        1. Deletes all files written during the failed installation.
        2. Restores original files from backups.
        """
        logger.warning("Iniciando rollback transacional...")

        for wf in written_files:
            try:
                if wf.is_file():
                    wf.unlink()
                    logger.debug(f"Rollback: removido arquivo gravado {wf.name}")
            except Exception as e:
                logger.error(f"Erro ao remover arquivo no rollback: {wf} ({e})")

        for orig, bak in created_backups.items():
            try:
                orig.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(bak, orig)
                logger.info(f"Rollback: restaurado {orig.name} a partir do backup.")
            except Exception as e:
                logger.error(f"Erro ao restaurar backup {bak} para {orig}: {e}")
