"""
Unified Browser Download Automator.
Implements the official priority hierarchy:
1. Official Chromium/Brave CDP (semantic DOM inspection, challenge detection, official countdown)
2. Controlled fallback (manual browser download with active filesystem monitoring)
"""

import asyncio
import logging
import webbrowser
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.panel import Panel

from .cdp_client import CdpClient
from .dom_actions import (
    get_check_challenges_js,
    get_check_countdown_js,
    get_click_manual_download_js,
    get_click_slow_download_js,
)
from .download_watcher import DownloadWatcher

logger = logging.getLogger(__name__)


class BrowserDownloadAutomator:
    """
    Automates the official Nexus Mods web UI download flow (Manual Download -> Slow Download)
    using Chromium DevTools Protocol when available, with resilient fallback to manual browser download.
    """

    def __init__(
        self,
        downloads_dir: Path | None = None,
        cdp_endpoint: str = "http://127.0.0.1:9222",
        console: Console | None = None,
    ):
        self.downloads_dir = downloads_dir or (Path.home() / "Downloads")
        self.cdp_endpoint = cdp_endpoint
        self.console = console or Console()

    def find_existing_local_download(
        self,
        mod_id: int | None,
        mod_name: str | None,
        file_id: int | None = None,
    ) -> Path | None:
        """Checks if a matching archive is already present in downloads_dir or ./mods."""
        candidate_dirs = [self.downloads_dir, Path("mods")]
        for d in candidate_dirs:
            if d.is_dir():
                for f in d.glob("*"):
                    if f.is_file() and f.suffix.lower() in (".zip", ".rar", ".7z", ".tar.gz"):
                        if DownloadWatcher.is_matching_mod(f.name, mod_id, mod_name, file_id):
                            return f
        return None

    async def download_mod_file(
        self,
        game_domain: str,
        mod_id: int,
        file_id: int | None = None,
        mod_name: str | None = None,
        timeout: float = 120.0,
    ) -> Path | None:
        """
        Executes the official download flow with priority:
        CDP Semantic Automation -> Manual Browser Fallback -> Active Filesystem Watcher.
        """
        # 0. Check if file is already present
        existing = self.find_existing_local_download(mod_id, mod_name, file_id)
        if existing:
            self.console.print(f"[bold green]✓ Arquivo já presente localmente:[/bold green] [cyan]{existing.name}[/cyan]")
            return existing

        # 1. Capture baseline snapshot of ~/Downloads
        watcher = DownloadWatcher(self.downloads_dir)

        download_page = f"https://www.nexusmods.com/{game_domain}/mods/{mod_id}?tab=files"
        if file_id:
            download_page += f"&file_id={file_id}"

        # 2. Priority 1: Official CDP Automation (if port 9222 is active)
        cdp_client = CdpClient(self.cdp_endpoint)
        cdp_available = await cdp_client.is_available()

        if cdp_available:
            self.console.print("[bold green]✓ CDP oficial conectado no Brave/Chromium.[/bold green]")
            downloaded = await self._attempt_cdp_automation(
                cdp_client=cdp_client,
                download_page=download_page,
                mod_id=mod_id,
                file_id=file_id,
                mod_name=mod_name,
                watcher=watcher,
                timeout=timeout,
            )
            if downloaded:
                return downloaded
            self.console.print("[yellow]ℹ Automação via CDP não concluiu o download. Ativando fallback manual...[/yellow]")
        else:
            logger.debug(f"CDP endpoint not reachable at {self.cdp_endpoint}. Falling back to manual browser flow.")

        # 3. Priority 2: Controlled Fallback (Manual Browser Download + Active Watcher)
        return await self._execute_manual_fallback(
            download_page=download_page,
            mod_id=mod_id,
            file_id=file_id,
            mod_name=mod_name,
            watcher=watcher,
            timeout=timeout,
        )

    async def _attempt_cdp_automation(
        self,
        cdp_client: CdpClient,
        download_page: str,
        mod_id: int,
        file_id: int | None,
        mod_name: str | None,
        watcher: DownloadWatcher,
        timeout: float,
    ) -> Path | None:
        """Attempts semantic interaction with the Nexus page using CDP."""
        try:
            # Look for an existing tab with this mod or open it
            tabs = await cdp_client.list_tabs()
            target_tab: dict[str, Any] | None = None

            for tab in tabs:
                tab_url = tab.get("url", "")
                if f"mods/{mod_id}" in tab_url:
                    target_tab = tab
                    break

            if not target_tab:
                # Open page in browser
                try:
                    webbrowser.open(download_page)
                    await asyncio.sleep(2.0)
                    tabs = await cdp_client.list_tabs()
                    for tab in tabs:
                        if f"mods/{mod_id}" in tab.get("url", ""):
                            target_tab = tab
                            break
                except Exception as e:
                    logger.debug(f"Error opening browser tab: {e}")

            if not target_tab or not target_tab.get("webSocketDebuggerUrl"):
                logger.debug("Could not resolve target tab WebSocket debugger URL.")
                return None

            attached = await cdp_client.attach_to_tab(target_tab["webSocketDebuggerUrl"])
            if not attached:
                return None

            # Ensure tab is on the files/download page
            current_url = target_tab.get("url", "")
            if "tab=files" not in current_url:
                try:
                    await cdp_client.ws.call("Page.navigate", {"url": download_page})
                    await asyncio.sleep(2.5)
                except Exception as e:
                    logger.debug(f"Page.navigate exception: {e}")

            # Suppress "Save As" / file chooser dialogs and set direct download directory
            if cdp_client.ws:
                try:
                    await cdp_client.ws.call("Page.enable", {})
                    await cdp_client.ws.call(
                        "Page.setDownloadBehavior",
                        {
                            "behavior": "allow",
                            "downloadPath": str(self.downloads_dir.resolve()),
                        },
                    )
                except Exception as e:
                    logger.debug(f"Page.setDownloadBehavior exception: {e}")

            # Step A: Check for Cloudflare / CAPTCHA / Login challenges
            challenge_info = await cdp_client.evaluate(get_check_challenges_js())
            if isinstance(challenge_info, dict) and challenge_info.get("challenge"):
                challenge_type = challenge_info.get("type", "VERIFICATION")
                self.console.print()
                self.console.print(
                    Panel(
                        f"[bold red]O Nexus Mods apresentou uma etapa de verificação humana ({challenge_type}).[/bold red]\n\n"
                        f"Por favor, complete a confirmação necessária diretamente na janela aberta no navegador.\n\n"
                        f"[bold green]O AutoInstaller aguarda a conclusão e continuará automaticamente.[/bold green]",
                        title="[bold yellow]⚠ AÇÃO DO USUÁRIO NECESSÁRIA NO NAVEGADOR[/bold yellow]",
                        border_style="yellow",
                    )
                )
                # Wait for user to resolve challenge (poll every 2s)
                for _ in range(30):
                    await asyncio.sleep(2.0)
                    ch = await cdp_client.evaluate(get_check_challenges_js())
                    if isinstance(ch, dict) and not ch.get("challenge"):
                        self.console.print("[bold green]✓ Verificação humana concluída com sucesso.[/bold green]")
                        break

            # Step B & C: Robust multi-step interaction loop (Manual Download -> Requirements -> Slow Download)
            slow_clicked = False
            for step_idx in range(18):
                # 1. Check if Slow Download is directly available (e.g. on file download page)
                slow_res = await cdp_client.evaluate(get_click_slow_download_js())
                if isinstance(slow_res, dict) and slow_res.get("clicked"):
                    slow_clicked = True
                    break

                # 2. Otherwise, click Manual Download (handles Main files section & requirements modal)
                manual_res = await cdp_client.evaluate(get_click_manual_download_js(file_id))
                if isinstance(manual_res, dict) and manual_res.get("clicked"):
                    logger.info(f"CDP clicked Manual Download: {manual_res}")
                    stage = manual_res.get("stage", "MANUAL_DOWNLOAD")
                    btn_text = manual_res.get("text", "Manual download")
                    if "MAIN_FILES" in stage:
                        self.console.print(f"[dim]✓ Seção 'Main files' localizada: botão '{btn_text}' acionado via CDP.[/dim]")
                    elif stage == "REQUIREMENTS_MODAL":
                        self.console.print(f"[dim]✓ Confirmação de requisitos: botão '{btn_text}' acionado via CDP.[/dim]")
                    else:
                        self.console.print(f"[dim]✓ Botão '{btn_text}' acionado via CDP ({stage}).[/dim]")

                await asyncio.sleep(1.5)

            if slow_clicked:
                self.console.print("[bold green]✓ Botão 'Slow Download' acionado automaticamente via CDP.[/bold green]")

                # Step D: Respect official countdown (do not skip)
                countdown_info = await cdp_client.evaluate(get_check_countdown_js())
                if isinstance(countdown_info, dict) and countdown_info.get("countdown"):
                    secs = countdown_info.get("seconds_left", 5)
                    self.console.print(f"[dim]Aguardando contador oficial do Nexus ({secs}s)...[/dim]")
                    await asyncio.sleep(secs + 0.5)
                else:
                    await asyncio.sleep(5.0)

                # Step E: Wait for download in ~/Downloads
                downloaded_file = await watcher.wait_for_download(
                    mod_id=mod_id,
                    file_id=file_id,
                    mod_name=mod_name,
                    timeout=timeout,
                )
                if downloaded_file:
                    target_id = target_tab.get("id")
                    if target_id:
                        try:
                            await cdp_client.close_tab(target_id)
                            self.console.print(f"[bold green]✓ Aba do Mod #{mod_id} fechada automaticamente no navegador.[/bold green]")
                        except Exception as e:
                            logger.debug(f"Could not close tab {target_id}: {e}")
                    return downloaded_file

        except Exception as e:
            logger.debug(f"CDP interaction exception: {e}")
        finally:
            await cdp_client.close()

        return None

    async def _execute_manual_fallback(
        self,
        download_page: str,
        mod_id: int,
        file_id: int | None,
        mod_name: str | None,
        watcher: DownloadWatcher,
        timeout: float,
    ) -> Path | None:
        """Opens the official download page in browser and monitors filesystem for completed archive."""
        try:
            webbrowser.open(download_page)
        except Exception:
            pass

        panel_content = (
            f"[bold white]Mod:[/bold white] [cyan]{mod_name or f'Mod #{mod_id}'}[/cyan] (ID: {mod_id})\n\n"
            f"Como o download direto via API é restrito para contas Free/Supporter:\n\n"
            f"  [bold cyan]1.[/bold cyan] A página do mod foi aberta no seu navegador:\n"
            f"     [dim]{download_page}[/dim]\n"
            f"  [bold cyan]2.[/bold cyan] Clique em [bold green underline]Manual Download[/bold green underline] ➔ [bold green underline]Slow Download[/bold green underline].\n"
            f"  [bold cyan]3.[/bold cyan] O arquivo será salvo na sua pasta [bold cyan]Downloads[/bold cyan].\n\n"
            f"[bold green]O AutoInstaller detectará o download automaticamente e prosseguirá.[/bold green]"
        )

        self.console.print()
        self.console.print(
            Panel(
                panel_content,
                title="[bold yellow]⬇ AUTORIZAÇÃO DE DOWNLOAD (NEXUS FREE / SUPPORTER)[/bold yellow]",
                border_style="yellow",
            )
        )
        self.console.print("\n[dim]Aguardando o download em ~/Downloads (pressione Ctrl+C para cancelar)...[/dim]\n")

        downloaded = await watcher.wait_for_download(
            mod_id=mod_id,
            file_id=file_id,
            mod_name=mod_name,
            timeout=timeout,
        )

        if downloaded:
            self.console.print(f"[bold green]✓ Download detectado:[/bold green] [cyan]{downloaded.name}[/cyan] ({downloaded.stat().st_size} bytes)\n")
            try:
                cdp = CdpClient(self.cdp_endpoint)
                if await cdp.is_available():
                    tabs = await cdp.list_tabs()
                    for t in tabs:
                        if f"mods/{mod_id}" in t.get("url", "") and t.get("id"):
                            await cdp.close_tab(t["id"])
                            self.console.print(f"[bold green]✓ Aba do Mod #{mod_id} fechada automaticamente no navegador.[/bold green]")
                            break
            except Exception:
                pass
            return downloaded

        self.console.print(
            "\n[bold yellow]⚠ Tempo esgotado aguardando o download.[/bold yellow]\n"
            "[dim]A página permanece aberta no navegador. Quando quiser, baixe o arquivo e execute novamente.[/dim]\n"
        )
        return None
