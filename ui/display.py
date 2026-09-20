"""Rich display elements, tables, status cards, and final reports."""

import time
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from dependencies.resolver import InstallationPlan

console = Console()


def print_banner() -> None:
    """Print the application title banner."""
    title = Text("NEXUS MODS AUTO INSTALLER", style="bold cyan")
    subtitle = Text("High-Performance · Safe · Dependency-Aware · Official Compliant", style="dim")
    panel = Panel(
        Text.assemble(title, "\n", subtitle, justify="center"),
        border_style="bright_blue",
        padding=(1, 2),
    )
    console.print(panel)


def print_plan_summary(plan: InstallationPlan, dry_run: bool = False) -> None:
    """Display the resolved installation plan, dependencies, and execution sequence."""
    table = Table(title="Execution Plan Overview", border_style="cyan", header_style="bold magenta")
    table.add_column("Metric", style="bold")
    table.add_column("Count / Value", style="green")

    table.add_row("Mods Requested", str(len(plan.requested_mods)))
    table.add_row("Dependencies Discovered", str(len(plan.discovered_dependencies)))
    table.add_row("Total Components", str(len(plan.installation_order)))
    table.add_row("Already Installed", str(len(plan.already_installed)))
    table.add_row("Downloads Required", str(len(plan.to_download)))
    table.add_row("Total Download Size", f"{plan.total_download_bytes / (1024 * 1024):.2f} MB")

    console.print(table)

    # Print Installation Order
    order_table = Table(title="Topological Installation Order", border_style="blue", header_style="bold green")
    order_table.add_column("#", justify="right", style="dim")
    order_table.add_column("Mod Name", style="bold")
    order_table.add_column("Domain / ID", style="cyan")
    order_table.add_column("Role", style="yellow")
    order_table.add_column("Status", style="magenta")

    for idx, node in enumerate(plan.installation_order, start=1):
        role = "Target Mod" if node.is_requested else "Dependency"
        status = "[green]✓ Installed[/green]" if node.is_installed else "[yellow]Needs Download[/yellow]"
        order_table.add_row(str(idx), node.name, f"{node.game_domain}:{node.mod_id}", role, status)

    console.print(order_table)

    # Print External Requirements if any
    if plan.external_requirements:
        ext_table = Table(title="⚠ External Requirements (Manual Action Required)", border_style="yellow")
        ext_table.add_column("Component", style="bold")
        ext_table.add_column("Official Source", style="cyan")

        for ext in plan.external_requirements:
            ext_table.add_row(ext.target_name, ext.external_url or "Check official mod page")

        console.print(ext_table)

    if dry_run:
        console.print(
            Panel(
                "[bold yellow]DRY-RUN COMPLETE[/bold yellow]\nNo files were downloaded or installed.",
                border_style="yellow",
            )
        )


def generate_final_report(
    plan: InstallationPlan,
    download_metrics: dict[str, Any],
    installed_count: int,
    failed_count: int,
    start_time: float,
    log_dir: Path = Path("data/logs"),
) -> str:
    """Generate and save the final summary report."""
    elapsed = max(time.time() - start_time, 0.001)
    mins = int(elapsed // 60)
    secs = int(elapsed % 60)
    time_str = f"{mins:02d}:{secs:02d}"

    total_components = len(plan.installation_order)
    total_requested = len(plan.requested_mods)
    dependencies_count = len(plan.discovered_dependencies)
    already_installed_count = len(plan.already_installed)
    downloaded_count = download_metrics.get("successful_count", 0)
    total_mb = download_metrics.get("total_mb", 0.0)
    avg_speed = download_metrics.get("average_speed_mb_s", 0.0)

    report_lines = [
        "╔══════════════════════════════════════════════╗",
        "║            INSTALLATION COMPLETE             ║",
        "╠══════════════════════════════════════════════╣",
        f"║ Mods requested:            {total_requested:<18}║",
        f"║ Dependencies:              {dependencies_count:<18}║",
        f"║ Total components:          {total_components:<18}║",
        f"║ Already installed:         {already_installed_count:<18}║",
        f"║ Downloaded:                {downloaded_count:<18}║",
        f"║ Installed:                 {installed_count:<18}║",
        f"║ Failed:                    {failed_count:<18}║",
        f"║ Total data:                {total_mb:.2f} MB{' ' * max(0, 15 - len(f'{total_mb:.2f} MB'))}║",
        f"║ Average speed:             {avg_speed:.2f} MB/s{' ' * max(0, 13 - len(f'{avg_speed:.2f} MB/s'))}║",
        f"║ Time:                      {time_str:<18}║",
        "╚══════════════════════════════════════════════╝",
    ]
    report_text = "\n".join(report_lines)

    # Save to disk
    log_dir.mkdir(parents=True, exist_ok=True)
    report_path = log_dir / f"report_{time.strftime('%Y%m%d_%H%M%S')}.txt"
    report_path.write_text(report_text, encoding="utf-8")

    return report_text
