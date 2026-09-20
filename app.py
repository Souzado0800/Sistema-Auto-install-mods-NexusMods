"""
Nexus Mods AutoInstaller - Main Application Entrypoint.
Production-grade mod dependency resolver, concurrent downloader, and installer.
Supports My Summer Car / MSCLoader with L3 persistent cache, SingleFlight, and Staging.
"""

import asyncio
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

from browser import BrowserTabsSource, ClipboardSource, ManualURLSource, ModCollector, NormalizedModUrl, TextFileSource
from cache import CacheManager
from database import (
    CacheRepository,
    DatabaseConnection,
    DownloadStoreRepository,
    InstallationRepository,
    ModRepository,
    QueueRepository,
    UnmanagedRepository,
    init_db,
)
from dependencies import DependencyResolver, InstallationPlan
from downloads import DownloadFileStore, DownloadManager
from installer import (
    BackupManager,
    InstallationManager,
    ProfileManager,
    StagingWorkspace,
    StartupScanner,
)
from nexus import NexusApiClient, NexusRateLimiter, UserValidate
from ui import (
    console,
    generate_final_report,
    parse_arguments,
    print_banner,
    print_plan_summary,
)
from utils.logging import get_logger, setup_logging

logger = get_logger("nexus.app")


def load_config(config_path: str) -> dict[str, Any]:
    """Load settings from config file, falling back to defaults."""
    default_config = {
        "nexus_api_key": "",
        "game": "mysummercar",
        "game_domain": "mysummercar",
        "mod_loader": "mscloader",
        "mods_directory": "/home/souza/My Summer Car/Mods",
        "profile": "mysummercar",
        "max_metadata_requests": 8,
        "max_downloads": 4,
        "max_extractions": 2,
        "retry_attempts": 3,
        "cache_ttl": 3600,
        "install_optional_dependencies": False,
        "backup_existing_files": True,
        "verify_hashes": True,
        "resume_downloads": True,
        "browser_cdp_url": "http://127.0.0.1:9222",
        "data_dir": "data",
    }

    p = Path(config_path)
    if p.is_file():
        try:
            user_cfg = json.loads(p.read_text(encoding="utf-8"))
            default_config.update(user_cfg)
        except Exception as e:
            logger.warning(f"Failed to read config file {p}: {e}")

    return default_config


async def async_main(args: Any) -> int:
    """Async main workflow."""
    start_time = time.time()
    print_banner()

    # 1. Load configuration and setup logging
    config = load_config(args.config)
    data_dir = Path(config.get("data_dir", "data"))
    data_dir.mkdir(parents=True, exist_ok=True)
    setup_logging(log_dir=data_dir / "logs", console_output=False)

    # Determine game domain and mods directory
    game_domain = config.get("game_domain") or config.get("game", "mysummercar")
    mods_dir = Path(args.game_dir or config.get("mods_directory") or config.get("game_directory") or "/home/souza/My Summer Car/Mods")

    console.print(f"[bold cyan]Target Game:[/bold cyan] {game_domain} (Loader: {config.get('mod_loader', 'mscloader')})")
    console.print(f"[bold cyan]Mods Directory:[/bold cyan] {mods_dir}")

    # 2. Initialize Database & Repositories
    db_path = data_dir / "database.sqlite"
    db_conn = DatabaseConnection(db_path)
    init_db(db_conn)

    mod_repo = ModRepository(db_conn)
    queue_repo = QueueRepository(db_conn)
    inst_repo = InstallationRepository(db_conn)
    cache_repo = CacheRepository(db_conn)
    store_repo = DownloadStoreRepository(db_conn)
    unmanaged_repo = UnmanagedRepository(db_conn)

    cache_mgr = CacheManager(cache_repo, default_ttl=config.get("cache_ttl", 3600))
    file_store = DownloadFileStore(data_dir / "downloads", store_repo)

    profile_mgr = ProfileManager()
    backup_mgr = BackupManager(data_dir / "backups")
    staging_ws = StagingWorkspace(data_dir / "staging")
    inst_mgr = InstallationManager(inst_repo, profile_mgr, backup_mgr, staging_ws)

    # 3. Handle Startup Scan Command or Automatic Initial Scan
    scanner = StartupScanner(mods_dir, inst_repo, unmanaged_repo, game_domain=game_domain)
    if args.subcommand == "scan" or args.scan:
        console.print(f"\n[bold green]Scanning {mods_dir}...[/bold green]")
        summary = scanner.scan()
        console.print(f"Total files found: [cyan]{summary.total_files}[/cyan] ({summary.dll_count} DLLs, {summary.directories_count} directories)")
        console.print(f"Managed files: [green]{summary.managed_files_count}[/green]")
        console.print(f"Unmanaged pre-existing files: [yellow]{summary.unmanaged_files_count}[/yellow]")
        return 0

    # Auto initial scan if database is fresh
    if not inst_repo.list_all_installed(game_domain) and not unmanaged_repo.list_unmanaged_files(game_domain):
        scanner.scan()

    # 4. Handle Cache Command
    if args.subcommand == "cache":
        if args.cache_action == "clean":
            cleaned = file_store.clean_unused(active_keys=set())
            expired_l2 = cache_repo.cleanup_expired()
            console.print(f"[green]Cache cleaned:[/green] {cleaned} archives deleted, {expired_l2} expired metadata entries removed.")
        else:
            stats = file_store.stats(game_domain)
            l1_stats = cache_mgr.stats()
            console.print("\n[bold magenta]═══ Cache Status ═══[/bold magenta]")
            console.print(f"L1 Memory items: [cyan]{l1_stats['memory_items']}[/cyan] (Hits: {l1_stats['hits']}, Misses: {l1_stats['misses']})")
            console.print(f"L3 Cached archives: [cyan]{stats['total_files']}[/cyan] ({stats['total_mb']} MB)")
        return 0

    # 5. Handle Repair Mode
    if args.repair:
        console.print(f"[bold cyan]Auditing integrity for Mod ID #{args.repair}...[/bold cyan]")
        report = inst_mgr.repair_mod(game_domain, args.repair, mods_dir)
        console.print(report)
        return 0

    # 6. Handle Update Check Mode
    if args.check_updates:
        console.print("[bold cyan]Scanning installed mods for available updates...[/bold cyan]")
        installed = inst_repo.list_all_installed(game_domain)
        console.print(f"Found {len(installed)} installed mods.")
        return 0

    # 7. Collect Mod URLs via Pluggable ModSources
    use_cdp = args.collect_tabs or (args.subcommand == "tabs")
    raw_url_strings: list[str] = []

    if args.file:
        raw_url_strings.extend(await TextFileSource(args.file).collect())
    if args.urls:
        raw_url_strings.extend(await ManualURLSource(args.urls).collect())
    if use_cdp:
        raw_url_strings.extend(await BrowserTabsSource(cdp_url=args.cdp_url or config.get("browser_cdp_url")).collect())

    # Fallback to Clipboard if no inputs given and not resume
    if not raw_url_strings and not args.resume:
        clipboard_urls = await ClipboardSource().collect()
        if clipboard_urls:
            console.print(f"[cyan]Detected {len(clipboard_urls)} Nexus URL(s) on system clipboard.[/cyan]")
            raw_url_strings.extend(clipboard_urls)

    collector = ModCollector(cdp_endpoint=args.cdp_url or config.get("browser_cdp_url"))
    collected_mods: list[NormalizedModUrl] = await collector.collect(
        raw_urls=raw_url_strings,
        use_cdp=False,  # Already collected above
    )

    if not collected_mods and not args.resume:
        console.print("[bold yellow]No mod URLs found to process.[/bold yellow]")
        console.print("Usage examples:")
        console.print("  [cyan]python app.py --file mods.txt --dry-run[/cyan]")
        console.print("  [cyan]python app.py tabs[/cyan] (collect from open browser tabs)")
        console.print("  [cyan]python app.py scan[/cyan] (catalog current mods directory)")
        return 1

    console.print(f"[bold green]Collected {len(collected_mods)} unique mod(s) to process.[/bold green]")

    # 8. Credentials and API Client Setup
    api_key = args.api_key or config.get("nexus_api_key") or os.environ.get("NEXUS_API_KEY")
    rate_limiter = NexusRateLimiter()

    is_premium = False
    if api_key:
        try:
            client = NexusApiClient(
                api_key=api_key,
                cache_manager=cache_mgr,
                rate_limiter=rate_limiter,
            )
            user_info: UserValidate = await client.validate_key()
            is_premium = user_info.is_premium
            console.print(
                f"[cyan]Nexus Account:[/cyan] {user_info.name} "
                f"([bold {'green' if is_premium else 'yellow'}]{user_info.tier.upper()}[/bold {'green' if is_premium else 'yellow'}])"
            )
        except Exception as e:
            logger.warning(f"Could not validate Nexus API key: {e}")
            console.print(f"[yellow]Warning:[/yellow] Could not authenticate with Nexus API: {e}")
            client = NexusApiClient(api_key="mock", cache_manager=cache_mgr, rate_limiter=rate_limiter)
    else:
        console.print(
            "[yellow]Note:[/yellow] No NEXUS_API_KEY provided. Running in offline/simulation mode.\n"
            "Set NEXUS_API_KEY in environment or config.json to download directly from official CDN."
        )
        client = NexusApiClient(api_key="unauthenticated", cache_manager=cache_mgr, rate_limiter=rate_limiter)

    # 9. Resolve Dependencies and Build Installation Plan
    resolver = DependencyResolver(
        api_client=client,
        mod_repo=mod_repo,
        installation_repo=inst_repo,
        install_optional=config.get("install_optional_dependencies", False),
        concurrency_limit=config.get("max_metadata_requests", 8),
    )

    with console.status("[bold green]Resolving dependencies and analyzing mod tree..."):
        plan: InstallationPlan = await resolver.resolve_plan(collected_mods)

    # 10. Display Plan Summary
    print_plan_summary(plan, dry_run=args.dry_run)

    if args.dry_run:
        await client.close()
        return 0

    # 11. Concurrent Resumable Downloads with L3 Store & SingleFlight
    download_dir = data_dir / "downloads"
    download_mgr = DownloadManager(
        api_client=client,
        download_dir=download_dir,
        queue_repo=queue_repo,
        store_repo=store_repo,
        max_concurrent=args.max_downloads or config.get("max_downloads", 4),
    )

    if plan.to_download:
        console.print(f"\n[bold green]Processing {len(plan.to_download)} files (L3 Cache Check + Download)...[/bold green]")
        downloaded_archives = await download_mgr.execute_downloads(
            plan.to_download, is_premium=is_premium
        )
    else:
        downloaded_archives = []

    # 12. MSCLoader Smart Installation & Staging
    installed_count = 0
    failed_count = 0

    if downloaded_archives:
        console.print(f"\n[bold cyan]Deploying {len(downloaded_archives)} components to {mods_dir}...[/bold cyan]")
        for node in plan.installation_order:
            if node.is_installed:
                continue

            matching = [p for p in downloaded_archives if str(node.mod_id) in p.name or (node.file_id and str(node.file_id) in p.name)]
            if matching:
                archive = matching[0]
                result = inst_mgr.install_mod(node, archive, mods_dir)
                if result.success:
                    installed_count += 1
                else:
                    failed_count += 1
                    console.print(f"[red]Failed:[/red] {node.name} - {result.error_message}")
            else:
                if not is_premium and not node.download_url:
                    pass  # Free user awaiting authorization
                else:
                    failed_count += 1

    # 13. Final Metrics & Executive Report
    metrics = download_mgr.metrics()
    report_text = generate_final_report(
        plan=plan,
        download_metrics=metrics,
        installed_count=installed_count,
        failed_count=failed_count,
        start_time=start_time,
        log_dir=data_dir / "logs",
    )
    console.print(report_text)

    await client.close()
    return 0 if failed_count == 0 else 1


def main() -> None:
    """Sync entrypoint wrapper."""
    args = parse_arguments()
    exit_code = asyncio.run(async_main(args))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
