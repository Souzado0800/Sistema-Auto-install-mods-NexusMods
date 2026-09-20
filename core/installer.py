"""
Transactional AutoInstaller for MSCLoader mods.
Combines AutoInstallModMySummerCar heuristics (ownership tracking, conflict isolation,
README formatting, _Backups/) with SQLite WAL persistence and Zip Slip sandboxing.
"""

from pathlib import Path
import hashlib

from core.analyzer import ModPackage, ModAnalyzer
from core.backups import MSCBackupManager
from core.readers import open_archive
from core.resolver import PathResolver
from database.connection import DatabaseConnection
from database.repositories import OwnershipRepository, InstallationRepository
from utils.logging import get_logger

logger = get_logger("core.installer")


def calculate_bytes_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def calculate_file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


class AutoInstaller:
    def __init__(
        self,
        mods_dir: Path | str,
        db_conn: DatabaseConnection | None = None,
        backup_manager: MSCBackupManager | None = None,
    ):
        self.mods_dir = Path(mods_dir).resolve()
        self.backup_mgr = backup_manager or MSCBackupManager(self.mods_dir)
        self.ownership_repo = OwnershipRepository(db_conn) if db_conn else None
        self.installation_repo = InstallationRepository(db_conn) if db_conn else None
        self.path_resolver = PathResolver(
            self.mods_dir,
            db_ownership_fn=self.ownership_repo.get_owner if self.ownership_repo else None,
        )

        self.analyzer = ModAnalyzer()
        self.last_conflicts_count = 0

    def install_package(self, pkg: ModPackage, game_domain: str = "mysummercar", mod_id: int = 0) -> bool:
        """
        Transactional mod package installation:
        1. Resolves and sanitizes destination paths.
        2. Backs up existing files destined to be updated into _Backups/.
        3. Isolates collisions between distinct mods (preserves existing files).
        4. Safely writes members to disk.
        5. Validates physical integrity (size and SHA-256).
        6. Records ownership and manifest state in SQLite WAL.
        7. On any failure, performs atomic rollback of written files and restores backups.
        """
        self.last_conflicts_count = 0
        written_files: list[Path] = []
        created_backups: dict[Path, Path] = {}
        installed_info: dict[str, tuple[str, int]] = {}

        if not pkg.members:
            if not self.analyzer.analyze_package(pkg):
                logger.error(f"Falha ao analisar pacote {pkg.filename}")
                return False

        if not pkg.resolved_mappings:
            if not self.path_resolver.resolve_package_paths(pkg):
                logger.error(f"Falha ao resolver caminhos para {pkg.filename}")
                return False


        try:
            with open_archive(pkg.file_path) as reader:
                for member_name, rel_target in pkg.resolved_mappings.items():
                    dest_path = (self.mods_dir / rel_target).resolve()
                    data = reader.read_bytes(member_name)

                    # Formatar README se aplicável
                    if rel_target.lower().startswith("readme") and rel_target.lower().endswith(".md"):
                        try:
                            text = data.decode("utf-8", errors="replace")
                            if not text.startswith("# "):
                                title = pkg.mod_name_detected or pkg.filename
                                data = f"# {title} - Informações\n\n{text}".encode()
                        except Exception:
                            pass

                    new_hash = calculate_bytes_sha256(data)
                    new_size = len(data)

                    # Verificar colisão entre mods distintos
                    if dest_path.is_file():
                        existing_hash = calculate_file_sha256(dest_path)
                        owner = self.ownership_repo.get_owner(rel_target) if self.ownership_repo else None
                        is_different_mod = False
                        if owner:
                            owner_group = owner.get("mod_group", "")
                            pkg_group = pkg.base_group_name or pkg.mod_name_detected
                            if owner_group and pkg_group and owner_group.lower() != pkg_group.lower():
                                is_different_mod = True

                        if is_different_mod:
                            if existing_hash == new_hash:
                                # Arquivo idêntico compartilhado entre mods (ex: RaycastCore.dll)
                                installed_info[rel_target] = (existing_hash, new_size)
                                if self.ownership_repo:
                                    self.ownership_repo.record_ownership(
                                        rel_target, pkg.mod_name_detected, pkg.base_group_name, existing_hash, is_shared=True
                                    )
                                continue
                            else:
                                # Conflito entre mods distintos com conteúdo divergente
                                owner_name = owner.get("mod_name", "outro mod")
                                logger.warn(f"Conflito isolado em {rel_target}: já gerenciado por '{owner_name}'. Mantendo versão existente.")
                                self.last_conflicts_count += 1
                                continue
                        else:
                            # Mesmo mod ou mod não gerenciado: se arquivo mudou, cria backup
                            if existing_hash != new_hash:
                                bak = self.backup_mgr.create_backup(dest_path)
                                if bak:
                                    created_backups[dest_path] = bak

                    # Cria diretórios pais com segurança
                    dest_path.parent.mkdir(parents=True, exist_ok=True)

                    with open(dest_path, "wb") as f:
                        f.write(data)
                    written_files.append(dest_path)
                    installed_info[rel_target] = (new_hash, new_size)

            # Validação de integridade física pós-gravação
            for rel_target, (exp_hash, exp_size) in installed_info.items():
                chk_path = self.mods_dir / rel_target
                if not chk_path.is_file() or chk_path.stat().st_size != exp_size:
                    raise RuntimeError(f"Falha de integridade física após gravação em {rel_target}")
                real_hash = calculate_file_sha256(chk_path)
                if real_hash != exp_hash:
                    raise RuntimeError(f"Hash mismatch pós-gravação em {rel_target}: esperado {exp_hash}, obtido {real_hash}")

            # Gravar no repositório de persistência SQLite WAL
            if self.ownership_repo:
                for rel_target, (h, _) in installed_info.items():
                    self.ownership_repo.record_ownership(
                        rel_target, pkg.mod_name_detected, pkg.base_group_name, h
                    )

            if self.installation_repo and mod_id:
                manifest_files = [
                    {"relative_path": rel, "file_size": sz, "sha256": h}
                    for rel, (h, sz) in installed_info.items()
                ]
                self.installation_repo.record_installation(
                    game_domain=game_domain,
                    mod_id=mod_id,
                    file_id=0,
                    mod_name=pkg.mod_name_detected or pkg.filename,
                    version=pkg.version_detected or "1.0",
                    profile="mysummercar",
                    install_dir=str(self.mods_dir),
                    manifest=manifest_files,
                )

            logger.info(f"Mod {pkg.filename} instalado com sucesso em {self.mods_dir}")
            return True

        except Exception as e:
            logger.error(f"Erro transacional ao instalar {pkg.filename}: {e}. Executando rollback...")
            self.backup_mgr.rollback(written_files, created_backups)
            return False

    def install_archive(self, archive_path: Path | str, game_domain: str = "mysummercar", mod_id: int = 0) -> bool:
        pkg = ModPackage(archive_path)
        if not self.analyzer.analyze_package(pkg):
            return False
        return self.install_package(pkg, game_domain=game_domain, mod_id=mod_id)
