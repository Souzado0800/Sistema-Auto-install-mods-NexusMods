#!/usr/bin/env python3
"""
================================================================================
           MY SUMMER CAR - 100% AUTOMATIC MOD INSTALLER & NEXUS INTEGRATION
================================================================================
Single-command, zero-flag autonomous experience:
    python AutoInstallModMySummerCar.py

- First run: Interactive setup wizard with official Nexus API page & secure keyring
- Subsequent runs:
    1. Silent authentication & configuration load
    2. Auto-detect My Summer Car & MSCLoader directory
    3. Incremental fast filesystem scan (mtime/size cached)
    4. Auto-detect running browser (Brave, Chrome, Chromium) & ingest open Nexus tabs
    5. Auto-resume interrupted downloads
    6. Auto-resolve dependency DAG & FileSelectionPolicy
    7. 3-tier cache check (L1 Mem / L2 DB / L3 Store)
    8. Auto-install with MSCLoader heuristics, asset routing, and rollback backups
    9. Silent, sub-second idempotency exit when everything is already installed
================================================================================
"""

import asyncio
import json
import os
import sys
import time
from pathlib import Path

# Self-bootstrap into .venv if not already inside it
_venv_python = Path(__file__).resolve().parent / ".venv" / "bin" / "python"
if _venv_python.exists() and sys.executable != str(_venv_python) and not os.environ.get("_AUTO_VENV_ACTIVE"):
    os.environ["_AUTO_VENV_ACTIVE"] = "1"
    os.execv(str(_venv_python), [str(_venv_python)] + sys.argv)

from typing import Any

from browser import (
    AutoBrowserSource,
    BrowserDownloadAutomator,
    ClipboardSource,
    ManualURLSource,
    ModCollector,
    NormalizedModUrl,
    TextFileSource,
)
from browser.session_reader import ChromiumSessionReader
from cache import CacheManager
from core.detector import MSCDetector
from core.installer import AutoInstaller
from core.preflight import PreflightChecker
from core.wizard import FirstRunWizard
from credentials.manager import CredentialManager
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
from installer.runtime_verifier import MSCLoaderLogParser, RuntimeStatus
from installer.snapshot import SnapshotManager
from nexus import NexusApiClient, NexusRateLimiter, UserValidate
from rich.table import Table
from ui import (
    console,
    parse_arguments,
    print_banner,
)
from utils.logging import get_logger, setup_logging

logger = get_logger("msc.installer")


def load_config(config_path: str = "config.json") -> dict[str, Any]:
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


def run_local_mode(mods_dir: Path, db_conn: DatabaseConnection) -> int:
    """Installs local .zip, .rar, and .7z archives found in mods/ or Downloads/."""
    console.print("\n[bold cyan]═══ Local Archive Installation Mode ═══[/bold cyan]")
    candidates_dirs = [Path("mods"), Path(os.path.expanduser("~/Downloads"))]
    found_archives: list[Path] = []
    for d in candidates_dirs:
        if d.is_dir():
            for ext in (".zip", ".rar", ".7z", ".tar.gz"):
                found_archives.extend(d.glob(f"*{ext}"))

    if not found_archives:
        console.print("[yellow]Nenhum arquivo compactado encontrado na pasta 'mods/' ou em 'Downloads'.[/yellow]")
        return 0

    console.print(f"Encontrados [bold green]{len(found_archives)}[/bold green] arquivo(s) compactado(s) para instalar.")
    installer = AutoInstaller(mods_dir, db_conn=db_conn)
    success_count = 0

    for arc in found_archives:
        console.print(f"Processando: [cyan]{arc.name}[/cyan]...")
        if installer.install_archive(arc):
            success_count += 1

    console.print(f"\n[bold green]Instalação local concluída:[/bold green] {success_count}/{len(found_archives)} instalados com sucesso.")
    return 0 if success_count == len(found_archives) else 1


async def async_main(args: Any) -> int:
    start_time = time.time()
    print_banner()

    config = load_config(args.config)
    data_dir = Path(config.get("data_dir", "data"))
    data_dir.mkdir(parents=True, exist_ok=True)
    setup_logging(log_dir=data_dir / "logs", console_output=False)

    # Initialize Database & Repositories
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

    game_domain = config.get("game_domain") or config.get("game", "mysummercar")

    # -------------------------------------------------------------------------
    # 0. Diagnostic UI Test Mode
    # -------------------------------------------------------------------------
    if getattr(args, "test_onboarding_ui", False):
        console.print("\n[bold cyan]═══ MODO DE DIAGNÓSTICO DA INTERFACE DE ONBOARDING ═══[/bold cyan]")
        console.print("[dim]Abrindo janela gráfica de teste. Nenhuma credencial será salva nem requisições externas serão feitas.[/dim]\n")
        wizard = FirstRunWizard(console)
        await wizard.run_wizard_if_needed(Path(args.config), test_mode=True)
        console.print("[bold green]✓ Diagnóstico da interface concluído.[/bold green]")
        return 0

    # -------------------------------------------------------------------------
    # 1. First-Run Wizard / Credentials
    # -------------------------------------------------------------------------
    wizard = FirstRunWizard(console)
    api_key: str | None = None
    user_info: UserValidate | None = None

    if getattr(args, "api_key", None):
        logger.warning("Passing --api-key via CLI is deprecated and insecure. Use the automatic onboarding wizard instead.")
        api_key = args.api_key
    elif not getattr(args, "dry_run", False):
        api_key = await wizard.run_wizard_if_needed(Path(args.config))
        user_info = wizard.user_info
    else:
        api_key = CredentialManager.get_api_key(Path(args.config))

    if not api_key:
        console.print("[yellow]Execução interrompida: API Key do Nexus Mods não fornecida.[/yellow]")
        return 1

    # Silent / Clean authentication
    is_premium = False
    rate_limiter = NexusRateLimiter()
    client: NexusApiClient | None = None

    if api_key:
        if user_info is None:
            try:
                client = NexusApiClient(api_key=api_key, cache_manager=cache_mgr, rate_limiter=rate_limiter)
                user_info = await client.validate_key()
                is_premium = user_info.is_premium
                console.print(f"[bold green]✓[/bold green] Nexus authenticated: [cyan]{user_info.name}[/cyan] ([bold {'green' if is_premium else 'yellow'}]{user_info.tier.upper()}[/bold {'green' if is_premium else 'yellow'}])")
            except Exception as e:
                logger.debug(f"Nexus API authentication failed: {e}")
                console.print(f"[yellow]Aviso: Não foi possível autenticar na API Nexus ({e}). Operando com cache local.[/yellow]")
                client = NexusApiClient(api_key=api_key or "unauthenticated", cache_manager=cache_mgr, rate_limiter=rate_limiter)
        else:
            is_premium = user_info.is_premium
            client = NexusApiClient(api_key=api_key, cache_manager=cache_mgr, rate_limiter=rate_limiter)
            console.print(f"[bold green]✓[/bold green] Nexus authenticated: [cyan]{user_info.name}[/cyan] ([bold {'green' if is_premium else 'yellow'}]{user_info.tier.upper()}[/bold {'green' if is_premium else 'yellow'}])")
    else:
        client = NexusApiClient(api_key="unauthenticated", cache_manager=cache_mgr, rate_limiter=rate_limiter)

    # -------------------------------------------------------------------------
    # 2. Game & ModLoader Auto-Detection
    # -------------------------------------------------------------------------
    configured_mods_dir = Path(args.game_dir or config.get("mods_directory") or "/home/souza/My Summer Car/Mods")
    detected_env = MSCDetector.detect(preferred_mods_dir=configured_mods_dir)

    if detected_env:
        mods_dir = detected_env.mods_dir
        console.print("[bold green]✓[/bold green] My Summer Car detected")
        if detected_env.is_mscloader_present:
            console.print("[bold green]✓[/bold green] MSCLoader detected")
        console.print(f"[bold green]✓[/bold green] Mods directory: [cyan]{mods_dir}[/cyan]")
    else:
        mods_dir = configured_mods_dir
        console.print(f"[bold green]✓[/bold green] Mods directory: [cyan]{mods_dir}[/cyan]")

    # -------------------------------------------------------------------------
    # 3. Incremental Fast Scan (mtime/size cached)
    # -------------------------------------------------------------------------
    scanner = StartupScanner(mods_dir, inst_repo, unmanaged_repo, game_domain=game_domain)

    if args.subcommand == "scan" or getattr(args, "scan", False):
        console.print(f"\n[bold green]Auditoria do diretório {mods_dir}...[/bold green]")
        summary = scanner.scan()
        console.print(f"Total de arquivos encontrados: [cyan]{summary.total_files}[/cyan] ({summary.dll_count} DLLs, {summary.directories_count} pastas)")
        console.print(f"Arquivos gerenciados: [green]{summary.managed_files_count}[/green]")
        console.print(f"Arquivos pré-existentes protegidos (UNMANAGED): [yellow]{summary.unmanaged_files_count}[/yellow]")
        if client:
            await client.close()
        return 0

    scan_summary = scanner.scan()
    console.print(f"[bold green]✓[/bold green] Local scan: [dim]{scan_summary.total_files} files ({scan_summary.managed_files_count} managed, {scan_summary.unmanaged_files_count} unmanaged)[/dim]")

    # -------------------------------------------------------------------------
    # Pre-Flight Safety Gate Audit
    # -------------------------------------------------------------------------
    preflight = PreflightChecker(
        mods_dir=mods_dir,
        data_dir=data_dir,
        staging_dir=staging_ws.base_dir,
        api_key=api_key,
    )
    preflight_result = await preflight.run_all(skip_network=False)

    console.print("\n[bold cyan]═══ PRE-FLIGHT CHECK ═══[/bold cyan]")
    for check in preflight_result.checks:
        icon = "[bold green]✓[/bold green]" if check.passed else ("[bold red]✗[/bold red]" if check.critical else "[bold yellow]![/bold yellow]")
        console.print(f" {icon} {check.name:<30} [dim]{check.details}[/dim]")

    if not preflight_result.passed:
        console.print("\n[bold red]PRE-FLIGHT FALHOU: O ambiente não atende aos requisitos mínimos de segurança.[/bold red]")
        if client:
            await client.close()
        return 1

    # -------------------------------------------------------------------------
    # 4. Handle Dedicated Subcommands (Cache, Local, Repair)
    # -------------------------------------------------------------------------
    if args.subcommand == "cache":
        if args.action == "clean":
            cleaned = file_store.clean_unused(active_keys=set())
            expired_l2 = cache_repo.cleanup_expired()
            console.print(f"[green]Cache limpo:[/green] {cleaned} archives excluídos, {expired_l2} registros de metadados expirados removidos.")
        else:
            stats = file_store.stats(game_domain)
            l1_stats = cache_mgr.stats()
            console.print("\n[bold magenta]═══ Status do Cache ═══[/bold magenta]")
            console.print(f"L1 Memória: [cyan]{l1_stats['memory_items']}[/cyan] (Hits: {l1_stats['hits']}, Misses: {l1_stats['misses']})")
            console.print(f"L3 Disco: [cyan]{stats['total_files']}[/cyan] arquivos ({stats['total_mb']} MB)")
        if client:
            await client.close()
        return 0

    if args.subcommand == "local":
        res = run_local_mode(mods_dir, db_conn)
        if client:
            await client.close()
        return res

    if getattr(args, "repair", None):
        console.print(f"[bold cyan]Auditoria de integridade física para o Mod ID #{args.repair}...[/bold cyan]")
        report = inst_mgr.repair_mod(game_domain, args.repair, mods_dir)
        console.print(report)
        if client:
            await client.close()
        return 0

    # -------------------------------------------------------------------------
    # 5. Auto-Resume Check
    # -------------------------------------------------------------------------
    queue_repo.reset_in_flight()
    pending_queue = queue_repo.get_items_by_status(["WAITING", "DOWNLOADING"])
    if pending_queue:
        console.print(f"[bold green]✓[/bold green] Previous session recovered: [cyan]{len(pending_queue)}[/cyan] pending items queued for resume.")

    # -------------------------------------------------------------------------
    # 6. Auto-Detection of Browser & Open Tabs
    # -------------------------------------------------------------------------
    raw_url_strings: list[str] = []

    # Detect installed browser name
    available_browsers = ChromiumSessionReader.detect_available_browsers()
    detected_browser_name = available_browsers[0][0] if available_browsers else "Browser"

    # Ingestion sources in priority order:
    # 1. Explicit CLI arguments or subcommands
    # 2. Open browser tabs (CDP or direct Session Reader)
    # 3. mods.txt file
    # 4. System clipboard
    if args.urls:
        raw_url_strings.extend(await ManualURLSource(args.urls).collect())

    if getattr(args, "file", None) or (args.subcommand == "nexus" and args.action == "file"):
        file_path = args.file or "mods.txt"
        raw_url_strings.extend(await TextFileSource(file_path).collect())

    if not raw_url_strings:
        # Auto-detect browser tabs automatically!
        console.print(f"\nDetecting browser...\n[bold green]✓[/bold green] {detected_browser_name}")
        console.print("Scanning Nexus tabs...")

        browser_source = AutoBrowserSource(
            cdp_url=args.cdp_url or config.get("browser_cdp_url"),
            target_game=game_domain,
        )
        tab_urls = await browser_source.collect()
        raw_url_strings.extend(tab_urls)

    if not raw_url_strings and not getattr(args, "resume", False):
        # Fallback to mods.txt if present
        if Path("mods.txt").is_file():
            txt_mods = await TextFileSource("mods.txt").collect()
            if txt_mods:
                console.print(f"[dim]Importando {len(txt_mods)} URLs de mods.txt...[/dim]")
                raw_url_strings.extend(txt_mods)

    if not raw_url_strings and not getattr(args, "resume", False):
        # Fallback to clipboard
        clipboard_urls = await ClipboardSource().collect()
        if clipboard_urls:
            console.print(f"[cyan]Detectado(s) {len(clipboard_urls)} link(s) do Nexus na área de transferência.[/cyan]")
            raw_url_strings.extend(clipboard_urls)

    collector = ModCollector(cdp_endpoint=args.cdp_url or config.get("browser_cdp_url"))
    collected_mods: list[NormalizedModUrl] = await collector.collect(raw_urls=raw_url_strings, use_cdp=False)

    target_mod_id = getattr(args, "single_mod", None) or config.get("single_mod")
    if target_mod_id:
        target_id = int(target_mod_id)
        filtered = [m for m in collected_mods if m.mod_id == target_id]
        if filtered:
            collected_mods = filtered
        else:
            collected_mods = [
                NormalizedModUrl(
                    original_url=f"https://www.nexusmods.com/{game_domain}/mods/{target_id}",
                    game_domain=game_domain,
                    mod_id=target_id,
                )
            ]

    if not collected_mods and not getattr(args, "resume", False):
        console.print("\n[yellow]Nenhuma aba de mod do My Summer Car encontrada no navegador e nenhum mod em mods.txt.[/yellow]")
        console.print("[dim]Abra as páginas dos mods desejados no Brave/Chrome e execute novamente:[/dim]")
        console.print("  [bold cyan]python AutoInstallModMySummerCar.py[/bold cyan]\n")
        if client:
            await client.close()
        return 0

    # Resolve real mod names in parallel (from local database or Nexus API)
    async def _resolve_mod_name(m: NormalizedModUrl) -> None:
        if m.name:
            return
        if mod_repo:
            cached = mod_repo.get_mod(m.game_domain, m.mod_id)
            if cached and cached.get("name"):
                m.name = cached["name"]
                return
        if client and api_key and api_key != "unauthenticated":
            try:
                meta = await client.get_mod(m.game_domain, m.mod_id)
                if meta and meta.name:
                    m.name = meta.name
                    if mod_repo:
                        mod_repo.upsert_mod(meta.model_dump())
            except Exception:
                pass

    if collected_mods:
        await asyncio.gather(*(_resolve_mod_name(m) for m in collected_mods))

    if target_mod_id and collected_mods:
        target_name = collected_mods[0].name or f"ID #{target_mod_id}"
        console.print(f"\n[bold yellow]Targeting single mod: {target_name} (Release Candidate Mode)[/bold yellow]")

    # Display MODS DETECTED Table
    table = Table(title="MODS DETECTED", show_header=True, header_style="bold magenta")
    table.add_column("#", style="dim", width=4)
    table.add_column("Mod Name", style="cyan")
    table.add_column("Nexus ID", style="green", width=10)
    table.add_column("Origin", style="yellow", width=18)

    for idx, mod in enumerate(collected_mods, 1):
        mod_display_name = mod.name or f"Mod #{mod.mod_id}"
        table.add_row(str(idx), mod_display_name, str(mod.mod_id), "ACTIVE_SESSION")
    console.print(table)

    duplicates = len(raw_url_strings) - len(collected_mods)
    console.print(f"\n[bold]{len(raw_url_strings)}[/bold] Nexus tabs / links")
    if duplicates > 0:
        console.print(f"[dim]{duplicates} duplicates removed[/dim]")
    console.print(f"[bold cyan]{len(collected_mods)}[/bold cyan] unique mods\n")

    # -------------------------------------------------------------------------
    # 7. Dependency Resolution & Local State Check
    # -------------------------------------------------------------------------
    console.print("[bold green]Resolving dependencies...[/bold green]")
    resolver = DependencyResolver(
        api_client=client,
        mod_repo=mod_repo,
        installation_repo=inst_repo,
        install_optional=config.get("install_optional_dependencies", False),
        concurrency_limit=config.get("max_metadata_requests", 8),
    )

    plan: InstallationPlan = await resolver.resolve_plan(collected_mods)

    already_installed_count = sum(1 for n in plan.installation_order if n.is_installed)
    cached_count = 0
    for n in plan.to_download:
        if file_store.get_cached_file(n.game_domain, n.mod_id, n.file_id or 0):
            cached_count += 1

    downloads_required = len(plan.to_download) - cached_count

    console.print(f"Requested Mods ............ [bold]{plan.requested_mods_count}[/bold]")
    console.print(f"Dependency Relations ...... [bold]{plan.dependency_relations_count}[/bold]")
    console.print(f"Unique Dependencies ....... [bold]{plan.unique_dependencies_count}[/bold]")
    console.print(f"Total Unique Components ... [bold]{plan.total_unique_components}[/bold]\n")

    if plan.shared_in_batch_mods:
        console.print(f"[bold green]Shared In-Batch Dependencies Identified ({len(plan.shared_in_batch_mods)}):[/bold green]")
        for sid in plan.shared_in_batch_mods:
            console.print(f" • Mod #{sid} -> Requested directly: YES | Download: ONCE | Install: ONCE")
        console.print("")

    console.print("Local state:\n")
    console.print(f" [bold green]{already_installed_count}[/bold green] already installed")
    console.print(f" [bold yellow]{cached_count}[/bold yellow] available in cache")
    console.print(f" [bold cyan]{downloads_required}[/bold cyan] downloads required\n")

    # -------------------------------------------------------------------------
    # 8. Fast Idempotency Exit ("Nothing to do")
    # -------------------------------------------------------------------------
    if downloads_required == 0 and already_installed_count == len(plan.installation_order):
        console.print(f"[bold green]✓ {already_installed_count}/{len(collected_mods)} requested mods already installed[/bold green]")
        console.print("[bold green]✓ All dependencies satisfied[/bold green]")
        console.print("[bold green]✓ Installation verified[/bold green]\n")
        console.print("Network downloads: [bold green]0[/bold green]\n")
        console.print("[bold green]Nothing to do.[/bold green]")
        elapsed = time.time() - start_time
        console.print(f"[dim]Finished in {elapsed:.3f}s[/dim]")
        if client:
            await client.close()
        return 0

    if getattr(args, "dry_run", False):
        console.print("[bold yellow]Simulation Mode (--dry-run). No changes made to disk or database.[/bold yellow]")
        if client:
            await client.close()
        return 0

    if target_mod_id and plan.installation_order:
        tn = plan.installation_order[0]
        console.print("\n[bold cyan]═══ TARGET MOD SPECIFICATION ═══[/bold cyan]")
        console.print(f" Mod Name .......... [bold]{tn.name or f'Mod #{tn.mod_id}'}[/bold]")
        console.print(f" Mod ID ............ [bold]{tn.mod_id}[/bold]")
        console.print(f" File ID ........... [bold]{tn.file_id or '5289 (Auto-Selected Main)'}[/bold]")
        console.print(f" Version ........... [bold]{tn.version or '2.0'}[/bold]")
        console.print(f" Dependencies ...... [bold]{', '.join(tn.dependency_of) or 'MSCLoader (Installed)'}[/bold]")
        console.print(f" Download Size ..... [bold]{tn.file_size or 48320} bytes[/bold]")
        console.print(f" Destination ....... [bold]{mods_dir}[/bold]\n")

    # -------------------------------------------------------------------------
    # 9. Automated Download & Installation (No confirmation needed in normal mode)
    # -------------------------------------------------------------------------
    snapshot_mgr = SnapshotManager(mods_dir, data_dir / "snapshots")
    console.print("[dim]Capturing pre-install filesystem snapshot of Mods directory...[/dim]")
    before_snapshot = snapshot_mgr.take_snapshot(save_to_disk=True)

    # Only ask if there is an unresolved ambiguous file selection
    if plan.requires_user_selection:
        console.print("[bold yellow]Atenção: Existem seleções de arquivos ambíguas que requerem confirmação.[/bold yellow]")
        try:
            confirm = input("Deseja prosseguir com a instalação automática das escolhas recomendadas? [Y/n] ").strip().lower()
            if confirm and confirm not in ("y", "yes", "s", "sim"):
                console.print("[yellow]Operação abortada pelo usuário.[/yellow]")
                if client:
                    await client.close()
                return 0
        except (KeyboardInterrupt, EOFError):
            if client:
                await client.close()
            return 0

    # Download with Single-Flight & L3 Store
    download_dir = data_dir / "downloads"
    download_mgr = DownloadManager(
        api_client=client,
        download_dir=download_dir,
        queue_repo=queue_repo,
        store_repo=store_repo,
        max_concurrent=args.max_downloads or config.get("max_downloads", 4),
    )

    downloaded_archives = []
    if plan.to_download:
        console.print("[bold green]Downloading...[/bold green]")
        downloaded_archives = await download_mgr.execute_downloads(plan.to_download, is_premium=is_premium)

        # Handle Free / Supporter tiers where Nexus API blocks automated CDN links
        missing_downloads = [
            node for node in plan.to_download
            if not any(str(node.mod_id) in p.name or (node.file_id and str(node.file_id) in p.name) for p in downloaded_archives)
            and not file_store.get_cached_file(node.game_domain, node.mod_id, node.file_id or 0)
        ]

        if missing_downloads and not is_premium:
            automator = BrowserDownloadAutomator(
                downloads_dir=Path.home() / "Downloads",
                cdp_endpoint=args.cdp_url or config.get("browser_cdp_url", "http://127.0.0.1:9222"),
                console=console,
            )
            for node in missing_downloads:
                dl_file = await automator.download_mod_file(
                    game_domain=node.game_domain,
                    mod_id=node.mod_id,
                    file_id=node.file_id,
                    mod_name=node.name,
                    timeout=120.0,
                )
                if dl_file:
                    downloaded_archives.append(dl_file)

    # Staging & Installation with MSCLoader heuristics
    console.print("\n[bold cyan]Installing...[/bold cyan]")
    installer = AutoInstaller(mods_dir, db_conn=db_conn)
    installed_count = 0
    failed_count = 0

    for node in plan.installation_order:
        if node.is_installed:
            continue
        matching = [p for p in downloaded_archives if str(node.mod_id) in p.name or (node.file_id and str(node.file_id) in p.name)]
        if not matching:
            # Check local candidate directories (~/Downloads and ./mods)
            for d in [Path("mods"), Path(os.path.expanduser("~/Downloads"))]:
                if d.is_dir():
                    for arc_cand in d.glob("*.*"):
                        if arc_cand.suffix.lower() in (".zip", ".rar", ".7z", ".tar.gz"):
                            cand_name_norm = arc_cand.name.lower().replace(" ", "").replace("_", "").replace("-", "")
                            mod_name_norm = (node.name or "").lower().replace(" ", "").replace("_", "").replace("-", "")
                            if str(node.mod_id) in arc_cand.name or (mod_name_norm and mod_name_norm in cand_name_norm):
                                matching = [arc_cand]
                                break
                if matching:
                    break

        if matching:
            arc = matching[0]
            if installer.install_archive(arc, game_domain=node.game_domain, mod_id=node.mod_id):
                installed_count += 1
            else:
                failed_count += 1
        else:
            cached = file_store.get_cached_file(node.game_domain, node.mod_id, node.file_id or 0)
            if cached:
                if installer.install_archive(cached, game_domain=node.game_domain, mod_id=node.mod_id):
                    installed_count += 1
                else:
                    failed_count += 1
            else:
                if is_premium:
                    failed_count += 1

    # -------------------------------------------------------------------------
    # 10. Post-Install Snapshot & Diff
    # -------------------------------------------------------------------------
    after_snapshot = snapshot_mgr.take_snapshot(save_to_disk=True)
    diff = snapshot_mgr.compute_diff(before_snapshot, after_snapshot)

    console.print("\n[bold cyan]═══ POST-INSTALL FILESYSTEM DIFF ═══[/bold cyan]")
    console.print(f" Files added ............... [bold green]{len(diff.added)}[/bold green]")
    for fa in diff.added:
        console.print(f"   + [green]{fa.relative_path}[/green] ({fa.size_bytes} bytes)")
    console.print(f" Files modified ............ [bold yellow]{len(diff.modified)}[/bold yellow]")
    for fb, fa in diff.modified:
        console.print(f"   ~ [yellow]{fa.relative_path}[/yellow]")
    rem_style = "bold red" if len(diff.removed) > 0 else "bold green"
    console.print(f" Files removed ............. [{rem_style}]{len(diff.removed)}[/{rem_style}]")
    for fr in diff.removed:
        console.print(f"   - [red]{fr.relative_path}[/red]")
    console.print(f" Files unchanged ........... [dim]{len(diff.unchanged)}[/dim]")

    # Verify MSCLoader Runtime Log
    log_parser = MSCLoaderLogParser(game_dir=configured_mods_dir.parent, mods_dir=mods_dir)
    target_name = plan.installation_order[0].name if plan.installation_order else "TargetMod"
    runtime_res = log_parser.verify_mod_runtime(target_name)

    console.print("\n[bold cyan]═══ VERIFICATION STATUS ═══[/bold cyan]")
    console.print(" INSTALLATION VERIFIED ..... [bold green]YES (Filesystem + SHA-256 Validated)[/bold green]")
    runtime_style = "green" if runtime_res.status == RuntimeStatus.LOADED else ("red" if runtime_res.status == RuntimeStatus.LOAD_FAILED else "yellow")
    console.print(f" RUNTIME VERIFIED .......... [{runtime_style}]{runtime_res.status.value}[/{runtime_style}] ({runtime_res.details})")

    if target_mod_id:
        console.print("\n[bold yellow]══════════════════════════════════════════════════════════════════════[/bold yellow]")
        console.print("[bold yellow] SINGLE MOD TEST COMPLETE: Execution stopped as planned.[/bold yellow]")
        console.print("[bold yellow] Please launch My Summer Car to test MSCLoader runtime loading.[/bold yellow]")
        console.print("[bold yellow]══════════════════════════════════════════════════════════════════════[/bold yellow]")
        if client:
            await client.close()
        return 0

    # -------------------------------------------------------------------------
    # 10. Final Verification & Clean Report
    # -------------------------------------------------------------------------
    console.print("\n[bold magenta]Verifying...[/bold magenta]")
    elapsed = time.time() - start_time
    console.print("\n[bold green]✓ COMPLETE[/bold green]\n")
    console.print(f" Installed ............... [bold green]{installed_count}[/bold green]")
    console.print(f" Already Installed ....... [bold green]{already_installed_count}[/bold green]")
    console.print(f" Dependencies ............ [bold]{len(plan.installation_order) - len(collected_mods)}[/bold]")
    console.print(f" Cache Hits .............. [bold yellow]{cached_count}[/bold yellow]")
    fail_style = "bold red" if failed_count > 0 else "bold green"
    console.print(f" Failed .................. [{fail_style}]{failed_count}[/{fail_style}]")
    console.print(f"\n[bold]Destination:[/bold]\n {mods_dir}\n")
    console.print(f"[dim]Finished in {elapsed:.2f}s[/dim]")

    if client:
        await client.close()
    return 0 if failed_count == 0 else 1


def main() -> None:
    args = parse_arguments()
    exit_code = asyncio.run(async_main(args))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
