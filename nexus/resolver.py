"""
Strict FileSelectionPolicy for Nexus Mods files.
Prioritizes MAIN FILE, handles applicable updates, ignores OLD files,
and requires explicit user selection when multiple conflicting MAIN files exist.
"""

from dataclasses import dataclass, field
from enum import StrEnum

from utils.logging import get_logger
from .models import FileCategory, ModFile

logger = get_logger("nexus.resolver")


class SelectionStatus(StrEnum):
    OK = "OK"
    USER_SELECTION_REQUIRED = "USER_SELECTION_REQUIRED"
    NO_FILES = "NO_FILES"


@dataclass
class FileSelectionResult:
    selected_files: list[ModFile] = field(default_factory=list)
    status: SelectionStatus = SelectionStatus.OK
    candidate_files: list[ModFile] = field(default_factory=list)
    reason: str = ""


class FileSelectionPolicy:
    """Implements strict file selection rules compliant with Nexus Mods standards."""

    @staticmethod
    def select_files(
        files: list[ModFile],
        preferred_file_id: int | None = None,
        allow_updates: bool = True,
        allow_optional: bool = False,
        allow_misc: bool = False,
    ) -> FileSelectionResult:
        if not files:
            return FileSelectionResult(status=SelectionStatus.NO_FILES, reason="Nenhum arquivo disponível para o mod.")

        # 1. Se um file_id explícito foi solicitado (ex.: link nxm://)
        if preferred_file_id:
            for f in files:
                if f.file_id == preferred_file_id:
                    return FileSelectionResult(
                        selected_files=[f],
                        status=SelectionStatus.OK,
                        reason=f"Arquivo preferencial explícito #{preferred_file_id} selecionado."
                    )

        # 2. Segregar por categoria
        main_files = [f for f in files if f.category_id == FileCategory.MAIN or f.is_main]
        update_files = [f for f in files if f.category_id == FileCategory.UPDATE]
        optional_files = [f for f in files if f.category_id == FileCategory.OPTIONAL]
        # OLD files (category 4) nunca são baixados automaticamente
        misc_files = [f for f in files if f.category_id == FileCategory.MISCELLANEOUS]

        # 3. Seleção de MAIN FILE
        selected: list[ModFile] = []
        if len(main_files) == 1:
            selected.append(main_files[0])
        elif len(main_files) > 1:
            primary = [f for f in main_files if f.is_primary]
            if len(primary) == 1:
                selected.append(primary[0])
            else:
                # Múltiplos MAIN files sem primário único: requer seleção do usuário
                return FileSelectionResult(
                    status=SelectionStatus.USER_SELECTION_REQUIRED,
                    candidate_files=main_files,
                    reason=f"Múltiplos MAIN FILES ({len(main_files)}) detectados sem primário inequívoco."
                )
        else:
            # Nenhum MAIN file explícito: busca nos outros que não sejam OLD
            non_old = [f for f in files if f.category_id != FileCategory.OLD_VERSION]
            if not non_old:
                return FileSelectionResult(
                    status=SelectionStatus.NO_FILES,
                    reason="Apenas arquivos marcados como OLD_VERSION encontrados."
                )
            # Ordena por timestamp decrescente
            sorted_recent = sorted(non_old, key=lambda x: x.uploaded_timestamp, reverse=True)
            selected.append(sorted_recent[0])

        # 4. Updates aplicáveis
        if allow_updates and update_files:
            # Adiciona o update mais recente se for mais novo que o MAIN selecionado
            latest_update = max(update_files, key=lambda x: x.uploaded_timestamp)
            if selected and latest_update.uploaded_timestamp > selected[0].uploaded_timestamp:
                selected.append(latest_update)

        # 5. Opcionais apenas mediante flag explícita
        if allow_optional and optional_files:
            selected.extend(optional_files)

        if allow_misc and misc_files:
            selected.extend(misc_files)

        return FileSelectionResult(
            selected_files=selected,
            status=SelectionStatus.OK,
            reason=f"Selecionado(s) {len(selected)} arquivo(s)."
        )


class FileResolver:
    """Helper wrapper for backward-compatibility with existing calls."""

    @staticmethod
    def select_main_file(files: list[ModFile], preferred_file_id: int | None = None) -> ModFile | None:
        res = FileSelectionPolicy.select_files(files, preferred_file_id=preferred_file_id)
        if res.selected_files:
            return res.selected_files[0]
        elif res.candidate_files:
            # Fallback para o mais recente se não bloqueado interativamente
            return sorted(res.candidate_files, key=lambda x: x.uploaded_timestamp, reverse=True)[0]
        return None
