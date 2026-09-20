"""
First-run interactive setup wizard for AutoInstallModMySummerCar.
Handles seamless, zero-config onboarding:
1. Detects missing or invalid Nexus API Key.
2. If graphical environment is present (Zorin OS / GNOME / X11 / Wayland), opens
   the native GTK 3 dialog with Ctrl+V, password masking, and async validation.
3. If headless/CLI-only, falls back to a verified controlling TTY with getpass.
4. Persists securely to OS Keyring (with 0600 file fallback).
5. Automatically continues the in-flight pipeline without restarting.
"""

import getpass
import logging
import sys
import webbrowser
from pathlib import Path

from credentials.manager import CredentialManager
from nexus.api import NexusApiClient
from nexus.models import UserValidate
from rich.console import Console
from rich.panel import Panel
from ui.onboarding_gui import NexusOnboardingWindow, is_gui_available

logger = logging.getLogger(__name__)

OFFICIAL_NEXUS_API_PAGE = "https://www.nexusmods.com/users/myaccount?tab=api"


class FirstRunWizard:
    """Guides the user through initial Nexus Mods API authentication."""

    def __init__(self, console: Console):
        self.console = console
        self.user_info: UserValidate | None = None

    def _open_api_page(self) -> None:
        """Opens the official Nexus Mods API settings page in the default browser."""
        opened = False
        try:
            opened = webbrowser.open(OFFICIAL_NEXUS_API_PAGE)
        except Exception:
            pass

        if not opened:
            self.console.print(
                f"[yellow]Não foi possível abrir o navegador automaticamente. Acesse:[/yellow]\n"
                f"{OFFICIAL_NEXUS_API_PAGE}\n"
            )

    async def run_wizard_if_needed(
        self, config_path: Path | None = None, test_mode: bool = False
    ) -> str | None:
        """
        Checks if an API key is present and valid. If missing or invalid, runs the interactive setup.
        Prefers native GUI on desktop, falling back to controlling TTY on headless environments.
        """
        if not test_mode:
            existing_key = CredentialManager.get_api_key(config_path)
            if existing_key:
                # Validate existing key silently
                client = NexusApiClient(api_key=existing_key)
                try:
                    self.user_info = await client.validate_key()
                    await client.close()
                    return existing_key
                except Exception as e:
                    await client.close()
                    logger.warning(f"Existing key invalid or rejected: {CredentialManager.redact(str(e))}")
                    self.console.print("\n[bold yellow]⚠ Chave de API anterior inválida ou revogada.[/bold yellow]\n")
                    CredentialManager.delete_api_key()

        # ---------------------------------------------------------------------
        # Option A: Native Graphical Onboarding (Preferred on Zorin / Desktop)
        # ---------------------------------------------------------------------
        if is_gui_available():
            if not test_mode:
                self._open_api_page()
            self.console.print("\n[bold cyan]Abrindo janela gráfica de configuração do Nexus Mods...[/bold cyan]")
            gui_window = NexusOnboardingWindow(config_path=config_path, test_mode=test_mode)
            validated_key = gui_window.run()
            if validated_key:
                self.user_info = gui_window.user_info
                self.console.print("[bold green]✓ Autenticação gráfica concluída com sucesso.[/bold green]\n")
                return validated_key
            else:
                self.console.print("[yellow]Configuração gráfica cancelada pelo usuário.[/yellow]")
                return None

        # ---------------------------------------------------------------------
        # Option B: Terminal Fallback (Headless / Non-GUI only)
        # ---------------------------------------------------------------------
        # Validate controlling TTY before prompting to prevent ghost / frozen input
        interactive_tty = None
        if sys.stdin.isatty():
            interactive_tty = sys.stdin
        else:
            try:
                interactive_tty = open("/dev/tty")
            except Exception:
                interactive_tty = None

        if interactive_tty is None:
            self.console.print("\n[bold red]ERROR: Interactive terminal unavailable.[/bold red]")
            self.console.print("[yellow]Não há interface gráfica disponível nem terminal interativo (/dev/tty).[/yellow]")
            return None

        self._open_api_page()

        panel_content = (
            "[bold white]A página da sua conta Nexus Mods foi aberta no navegador.[/bold white]\n\n"
            "[bold]Faça o seguinte:[/bold]\n\n"
            "  [bold cyan]1.[/bold cyan] Na página aberta, procure por:\n\n"
            "                 [bold green underline]Personal API Key[/bold green underline]\n\n"
            "  [bold cyan]2.[/bold cyan] Se ainda [bold red]NÃO[/bold red] existir uma chave, clique em:\n\n"
            "                 [bold green underline]Request API Key[/bold green underline]\n\n"
            "  [bold cyan]3.[/bold cyan] O Nexus Mods irá gerar sua Personal API Key.\n\n"
            "  [bold cyan]4.[/bold cyan] Copie a chave gerada.\n\n"
            "  [bold cyan]5.[/bold cyan] Volte para esta janela.\n\n"
            "  [bold cyan]6.[/bold cyan] Cole a chave no campo abaixo.\n\n"
            "[bold yellow]Se uma Personal API Key JÁ existir:[/bold yellow]\n\n"
            "      [bold]NÃO[/bold] gere outra.\n"
            "      Apenas copie a chave existente.\n\n"
            "[bold red]⚠ NÃO envie essa chave pelo ChatGPT, Antigravity, GitHub\n"
            "  ou qualquer outra conversa.[/bold red]\n\n"
            "[bold green]Ela deve ser colada SOMENTE aqui no AutoInstaller.[/bold green]"
        )
        self.console.print()
        self.console.print(
            Panel(
                panel_content,
                title="[bold yellow]⚠ CONFIGURAÇÃO DO NEXUS MODS[/bold yellow]",
                border_style="yellow",
                expand=False,
            )
        )

        self.console.print("\n[dim][R] Abrir novamente a página do Nexus | [Q] Cancelar configuração[/dim]\n")
        self.console.print("[bold cyan]Aguardando sua Personal API Key...[/bold cyan]\n")

        prompt_text = "Cole sua Nexus Personal API Key: "

        while True:
            try:
                user_input = getpass.getpass(prompt_text).strip()
            except (KeyboardInterrupt, EOFError):
                self.console.print("\n[yellow]Configuração cancelada pelo usuário.[/yellow]")
                return None

            if user_input.lower() == "r":
                self.console.print("\n[dim]Reabrindo a página do Nexus Mods no navegador...[/dim]")
                self._open_api_page()
                self.console.print(f"Página oficial: [bold underline cyan]{OFFICIAL_NEXUS_API_PAGE}[/bold underline cyan]\n")
                prompt_text = "Cole sua Nexus Personal API Key: "
                continue

            if user_input.lower() == "q":
                self.console.print("\n[yellow]Configuração cancelada pelo usuário.[/yellow]")
                return None

            if not user_input:
                self.console.print("[yellow]Chave vazia inserida. Tente novamente ou pressione Ctrl+C para sair.[/yellow]")
                continue

            api_key = user_input

            if test_mode:
                self.console.print(f"[bold green]✓ Modo de teste:[/bold green] Entrada recebida ({len(api_key)} caracteres).")
                return f"TEST_MODE_KEY_{len(api_key)}"

            self.console.print("\n[bold cyan]Validando Personal API Key com Nexus Mods...[/bold cyan]")
            client = NexusApiClient(api_key=api_key)
            try:
                user_info: UserValidate = await client.validate_key()
                self.user_info = user_info
                self.console.print("[bold green]✓ Personal API Key válida[/bold green]")
                self.console.print("[bold green]✓ Autenticação Nexus Mods concluída[/bold green]")
                self.console.print(
                    f"[bold green]✓ Conta detectada:[/bold green] {user_info.name} "
                    f"([bold {'green' if user_info.is_premium else 'yellow'}]{user_info.tier.upper()}[/bold {'green' if user_info.is_premium else 'yellow'}])"
                )

                CredentialManager.save_api_key(api_key, config_path)
                self.console.print("[bold green]✓ Credencial armazenada com segurança[/bold green]\n")
                self.console.print("[dim]Continuando automaticamente...[/dim]\n")
                await client.close()
                return api_key
            except Exception as e:
                await client.close()
                logger.warning(f"Nexus API key validation failed: {CredentialManager.redact(str(e))}")

                invalid_panel = (
                    "[bold red]O Nexus Mods rejeitou a chave informada.[/bold red]\n\n"
                    "Verifique se você copiou toda a\n"
                    "[bold green]Personal API Key[/bold green].\n\n"
                    "A página da API continua disponível no\n"
                    "navegador."
                )
                self.console.print()
                self.console.print(
                    Panel(
                        invalid_panel,
                        title="[bold red]API KEY INVÁLIDA[/bold red]",
                        border_style="red",
                        expand=False,
                    )
                )
                self.console.print("\n[dim][R] Reabrir página do Nexus | [Q] Cancelar[/dim]\n")
                prompt_text = "Cole novamente sua Personal API Key: "
