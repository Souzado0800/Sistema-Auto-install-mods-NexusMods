"""Rich multi-progress tracking for discovery, downloads, and installation."""


from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskID,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)


class MultiStageProgress:
    """Manages synchronized visual progress across pipeline phases."""

    def __init__(self):
        self.progress = Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            TransferSpeedColumn(),
            TimeRemainingColumn(),
            TimeElapsedColumn(),
        )
        self.discovery_task: TaskID | None = None
        self.download_task: TaskID | None = None
        self.install_task: TaskID | None = None

    def __enter__(self) -> "MultiStageProgress":
        self.progress.__enter__()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.progress.__exit__(exc_type, exc_val, exc_tb)

    def add_discovery_stage(self, total: int) -> TaskID:
        self.discovery_task = self.progress.add_task(
            "[cyan]Resolving Metadata & Dependencies...", total=total
        )
        return self.discovery_task

    def add_download_stage(self, total_bytes: int) -> TaskID:
        self.download_task = self.progress.add_task(
            "[green]Downloading Mods...", total=total_bytes
        )
        return self.download_task

    def add_install_stage(self, total: int) -> TaskID:
        self.install_task = self.progress.add_task(
            "[magenta]Extracting & Installing Mods...", total=total
        )
        return self.install_task

    def update_download(self, advance_bytes: int) -> None:
        if self.download_task is not None:
            self.progress.advance(self.download_task, advance_bytes)

    def update_install(self, advance_count: int = 1) -> None:
        if self.install_task is not None:
            self.progress.advance(self.install_task, advance_count)
