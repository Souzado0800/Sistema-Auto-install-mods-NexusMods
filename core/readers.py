"""
Archive readers supporting ZIP, TAR, and RAR archives for MSCLoader mod installation.
Uses /usr/bin/7z on Linux or system UnRAR for transparent RAR support.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
import os
import shutil
import subprocess
import zipfile
import tarfile

from utils.logging import get_logger

logger = get_logger("core.readers")


@dataclass
class ArchiveMember:
    filename: str
    file_size: int
    is_dir: bool

    def __post_init__(self):
        self.filename = self.filename.replace("\\", "/")


class BaseArchiveReader(ABC):
    @abstractmethod
    def get_members(self) -> list[ArchiveMember]:
        pass

    @abstractmethod
    def read_bytes(self, member_name: str) -> bytes:
        pass

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


class ZipReader(BaseArchiveReader):
    def __init__(self, archive_path: Path | str):
        self.archive_path = Path(archive_path)
        self.zip_file = zipfile.ZipFile(self.archive_path, 'r')

    def get_members(self) -> list[ArchiveMember]:
        members = []
        for info in self.zip_file.infolist():
            name = info.filename
            if info.flag_bits & 0x800 == 0:
                try:
                    name = name.encode('cp437').decode('utf-8', errors='replace')
                except Exception:
                    pass
            is_dir = info.is_dir() or name.endswith("/")
            members.append(ArchiveMember(name, info.file_size, is_dir))
        return members

    def read_bytes(self, member_name: str) -> bytes:
        norm = member_name.replace("\\", "/")
        for info in self.zip_file.infolist():
            if info.filename.replace("\\", "/") == norm:
                return self.zip_file.read(info)
        return self.zip_file.read(member_name)

    def close(self):
        self.zip_file.close()


class TarReader(BaseArchiveReader):
    def __init__(self, archive_path: Path | str):
        self.archive_path = Path(archive_path)
        self.tar_file = tarfile.open(self.archive_path, 'r:*')

    def get_members(self) -> list[ArchiveMember]:
        members = []
        for info in self.tar_file.getmembers():
            members.append(ArchiveMember(info.name, info.size, info.isdir()))
        return members

    def read_bytes(self, member_name: str) -> bytes:
        f = self.tar_file.extractfile(member_name)
        if f is None:
            raise FileNotFoundError(f"Member {member_name} not found or is a directory in TAR.")
        return f.read()

    def close(self):
        self.tar_file.close()


class RarReader(BaseArchiveReader):
    """Reads RAR archives using 7z (available on Linux /usr/bin/7z) or unrar CLI."""

    def __init__(self, archive_path: Path | str):
        self.archive_path = Path(archive_path)
        self.tool = self._find_tool()
        if not self.tool:
            raise RuntimeError(
                "Nenhuma ferramenta compatível com RAR (7z, 7za ou unrar) encontrada no sistema."
            )

    @staticmethod
    def _find_tool() -> str | None:
        local_7zz = Path(__file__).resolve().parent.parent / "bin" / "7zz"
        if local_7zz.is_file() and os.access(local_7zz, os.X_OK):
            return str(local_7zz)
        candidates = ["7zz", "unrar", "7z", "7za", "7zr", "/usr/bin/7zz", "/usr/bin/unrar", "/usr/bin/7z"]
        for c in candidates:
            found = shutil.which(c)
            if found:
                return found
        return None

    def get_members(self) -> list[ArchiveMember]:
        tool_lower = self.tool.lower()
        if "7z" in tool_lower:
            cmd = [self.tool, "l", "-slt", str(self.archive_path)]
            res = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
            if res.returncode != 0:
                raise RuntimeError(f"7-Zip erro ao listar RAR: {res.stderr}")

            members = []
            cur_path = None
            cur_size = 0
            cur_is_dir = False
            for line in res.stdout.splitlines():
                line = line.strip()
                if line.startswith("Path = "):
                    cur_path = line[7:]
                elif line.startswith("Size = "):
                    try:
                        cur_size = int(line[7:])
                    except ValueError:
                        cur_size = 0
                elif line.startswith("Folder = "):
                    cur_is_dir = (line[9:] == "+")
                elif line == "" and cur_path and cur_path != str(self.archive_path):
                    members.append(ArchiveMember(cur_path, cur_size, cur_is_dir))
                    cur_path = None
                    cur_size = 0
                    cur_is_dir = False
            if cur_path and cur_path != str(self.archive_path):
                members.append(ArchiveMember(cur_path, cur_size, cur_is_dir))
            return members
        else:
            cmd = [self.tool, "vb", str(self.archive_path)]
            res = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
            if res.returncode != 0:
                raise RuntimeError(f"UnRAR erro: {res.stderr}")
            members = []
            for line in res.stdout.splitlines():
                name = line.strip()
                if not name:
                    continue
                is_dir = name.endswith("/") or name.endswith("\\")
                members.append(ArchiveMember(name, 0, is_dir))
            return members

    def read_bytes(self, member_name: str) -> bytes:
        tool_lower = self.tool.lower()
        # 7z extracts to stdout with -so
        if "7z" in tool_lower:
            cmd = [self.tool, "e", "-so", str(self.archive_path), member_name]
        else:
            cmd = [self.tool, "p", "-inul", str(self.archive_path), member_name]

        res = subprocess.run(cmd, capture_output=True)
        if res.returncode != 0:
            raise RuntimeError(f"Falha ao extrair bytes do membro {member_name} no RAR: {res.stderr.decode('utf-8', errors='replace')}")
        return res.stdout


def open_archive(archive_path: Path | str) -> BaseArchiveReader:
    p = Path(archive_path)
    ext = p.suffix.lower()
    if ext in (".zip", ".jar"):
        return ZipReader(p)
    elif ext in (".tar", ".gz", ".tgz", ".bz2", ".xz"):
        return TarReader(p)
    elif ext == ".rar":
        return RarReader(p)
    else:
        raise ValueError(f"Formato de arquivo compactado não suportado: {ext}")
