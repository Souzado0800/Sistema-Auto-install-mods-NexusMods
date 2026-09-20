"""
Native GTK graphical onboarding window for AutoInstallModMySummerCar.
Provides a clean, intuitive first-setup UI for pasting and validating the Nexus Personal API Key.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import webbrowser
from pathlib import Path

# Ensure GTK 3 is imported via PyGObject
try:
    import gi
    gi.require_version("Gtk", "3.0")
    from gi.repository import GLib, Gtk
    GTK_AVAILABLE = True
except Exception:
    GTK_AVAILABLE = False
    Gtk = None
    GLib = None

from credentials.manager import CredentialManager
from nexus.api import NexusApiClient
from nexus.models import UserValidate

logger = logging.getLogger(__name__)

OFFICIAL_NEXUS_API_PAGE = "https://www.nexusmods.com/users/myaccount?tab=api"


def is_gui_available() -> bool:
    """Checks whether a graphical X11 or Wayland environment and GTK are available."""
    if not GTK_AVAILABLE:
        return False
    try:
        success, _ = Gtk.init_check()
        return bool(success)
    except Exception:
        return False


class NexusOnboardingWindow:
    """
    Lightweight, native GTK 3 dialog for initial Nexus API key onboarding.
    Features:
    - Native clipboard support (Ctrl+V, Shift+Insert, right-click context menu).
    - Masked password entry with Show/Hide checkbox.
    - Non-blocking asynchronous HTTP validation.
    - Diagnostic test mode (--test-onboarding-ui).
    """

    def __init__(self, config_path: Path | None = None, test_mode: bool = False):
        if not GTK_AVAILABLE:
            raise RuntimeError("GTK 3 (PyGObject) is not available in the current Python environment.")

        self.config_path = config_path
        self.test_mode = test_mode
        self.validated_key: str | None = None
        self.user_info: UserValidate | None = None

        self._build_ui()

    def _build_ui(self) -> None:
        # Main Window
        self.window = Gtk.Window(type=Gtk.WindowType.TOPLEVEL)
        self.window.set_title("AutoInstallModMySummerCar — Configuração do Nexus Mods")
        self.window.set_default_size(560, 490)
        self.window.set_position(Gtk.WindowPosition.CENTER)
        self.window.set_border_width(20)
        self.window.connect("destroy", self._on_window_destroy)

        # Root vertical layout
        root_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        self.window.add(root_box)

        # Title / Header
        title_label = Gtk.Label()
        mode_suffix = " <span color='#e5a50a'>(Modo de Teste)</span>" if self.test_mode else ""
        title_label.set_markup(f"<big><b>⚠ Configuração do Nexus Mods</b></big>{mode_suffix}")
        title_label.set_xalign(0.0)
        root_box.pack_start(title_label, False, False, 0)

        subtitle_label = Gtk.Label()
        subtitle_label.set_markup("A página da sua conta Nexus Mods foi aberta no navegador.")
        subtitle_label.set_xalign(0.0)
        root_box.pack_start(subtitle_label, False, False, 0)

        # Instructions Frame / Box
        instructions_frame = Gtk.Frame()
        instructions_frame.set_shadow_type(Gtk.ShadowType.ETCHED_IN)
        instructions_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        instructions_box.set_border_width(12)
        instructions_frame.add(instructions_box)
        root_box.pack_start(instructions_frame, False, False, 0)

        instructions_text = (
            "<b>Faça o seguinte:</b>\n\n"
            "  1. Na página aberta, procure por: <b><span color='#2ec27e'>Personal API Key</span></b>\n"
            "  2. Se ainda não existir uma chave, clique em: <b><span color='#2ec27e'>Request API Key</span></b>\n"
            "  3. Copie a chave gerada. <i>(Se já existir uma, apenas copie-a)</i>\n"
            "  4. Cole a chave no campo abaixo:"
        )
        inst_label = Gtk.Label()
        inst_label.set_markup(instructions_text)
        inst_label.set_xalign(0.0)
        instructions_box.pack_start(inst_label, False, False, 0)

        # Entry Section
        entry_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        root_box.pack_start(entry_box, False, False, 0)

        key_label = Gtk.Label()
        key_label.set_markup("<b>Personal API Key:</b>")
        key_label.set_xalign(0.0)
        entry_box.pack_start(key_label, False, False, 0)

        self.entry = Gtk.Entry()
        self.entry.set_visibility(False)
        self.entry.set_placeholder_text("Cole sua Personal API Key aqui...")
        self.entry.connect("activate", self._on_validate_clicked)
        entry_box.pack_start(self.entry, False, False, 0)

        # Checkbox: Mostrar chave
        self.check_show = Gtk.CheckButton(label="Mostrar chave")
        self.check_show.connect("toggled", self._on_toggle_visibility)
        entry_box.pack_start(self.check_show, False, False, 0)

        # Status / Feedback label
        self.status_label = Gtk.Label()
        self.status_label.set_use_markup(True)
        self.status_label.set_line_wrap(True)
        self.status_label.set_xalign(0.0)
        self.status_label.set_markup(
            "<small>🔒 A chave será armazenada de forma segura no Keyring do sistema.</small>"
        )
        root_box.pack_start(self.status_label, True, True, 0)

        # Action Buttons
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        root_box.pack_end(button_box, False, False, 0)

        self.btn_reopen = Gtk.Button(label="Abrir Nexus novamente")
        self.btn_reopen.connect("clicked", self._on_reopen_clicked)
        button_box.pack_start(self.btn_reopen, False, False, 0)

        # Right-aligned validate button
        self.btn_validate = Gtk.Button(label="Validar e continuar")
        self.btn_validate.get_style_context().add_class("suggested-action")
        self.btn_validate.connect("clicked", self._on_validate_clicked)
        button_box.pack_end(self.btn_validate, False, False, 0)

    def _on_toggle_visibility(self, button: Gtk.CheckButton) -> None:
        self.entry.set_visibility(button.get_active())

    def _on_reopen_clicked(self, _button: Gtk.Button) -> None:
        try:
            webbrowser.open(OFFICIAL_NEXUS_API_PAGE)
            self.status_label.set_markup("<small>Página reaberta no navegador.</small>")
        except Exception:
            self.status_label.set_markup(
                f"<small>Acesse no navegador: <b>{OFFICIAL_NEXUS_API_PAGE}</b></small>"
            )

    def _on_validate_clicked(self, _widget) -> None:
        raw_key = self.entry.get_text().strip()
        if not raw_key:
            self.status_label.set_markup(
                "<span color='#e5a50a'><b>⚠ Chave vazia:</b> Por favor, cole sua Personal API Key antes de continuar.</span>"
            )
            return

        # Diagnostics / Test Mode: verify keyboard, paste, and entry without calling Nexus
        if self.test_mode:
            key_len = len(raw_key)
            self.status_label.set_markup(
                f"<span color='#2ec27e'><b>✓ Teste Concluído com Sucesso!</b>\n"
                f"Entrada recebida: {key_len} caracteres.\n"
                f"Teclado, Ctrl+V e controles da interface estão 100% funcionais.\n"
                f"Nenhuma chave foi salva. Você pode fechar esta janela.</span>"
            )
            self.validated_key = f"TEST_MODE_KEY_{key_len}"
            return

        # Normal Mode: Asynchronous validation with official Nexus API
        self.status_label.set_markup("<span color='#3584e4'>⏳ Validando com Nexus Mods...</span>")
        self.btn_validate.set_sensitive(False)
        self.entry.set_sensitive(False)

        thread = threading.Thread(target=self._validate_worker, args=(raw_key,), daemon=True)
        thread.start()

    def _validate_worker(self, api_key: str) -> None:
        """Executes the asynchronous Nexus API validation on a background thread."""
        try:
            async def _do_validate() -> UserValidate:
                client = NexusApiClient(api_key=api_key)
                try:
                    return await client.validate_key()
                finally:
                    await client.close()

            user_info = asyncio.run(_do_validate())
            GLib.idle_add(self._on_validation_success, api_key, user_info)
        except Exception as exc:
            logger.warning(f"Nexus API validation failed in GUI: {CredentialManager.redact(str(exc))}")
            GLib.idle_add(self._on_validation_failure, str(exc))

    def _on_validation_success(self, api_key: str, user_info: UserValidate) -> None:
        self.user_info = user_info
        self.validated_key = api_key

        # Save to CredentialManager
        CredentialManager.save_api_key(api_key, self.config_path)

        tier_name = user_info.tier.upper() if hasattr(user_info, "tier") else "FREE"
        self.status_label.set_markup(
            f"<span color='#2ec27e'><b>✓ Personal API Key válida</b>\n"
            f"✓ Autenticação Nexus Mods concluída ({user_info.name} - {tier_name})\n"
            f"✓ Credencial armazenada com segurança no Keyring\n\n"
            f"<i>Continuando automaticamente...</i></span>"
        )

        # Close window automatically after brief visual confirmation
        GLib.timeout_add(700, self._close_and_quit)

    def _on_validation_failure(self, _error_msg: str) -> None:
        self.btn_validate.set_sensitive(True)
        self.entry.set_sensitive(True)
        self.status_label.set_markup(
            "<span color='#e01b24'><b>✗ O Nexus Mods rejeitou esta Personal API Key.</b>\n"
            "Confira se toda a chave foi copiada e tente novamente.</span>"
        )
        self.entry.select_region(0, -1)
        self.entry.grab_focus()

    def _close_and_quit(self) -> bool:
        self.window.destroy()
        return False

    def _on_window_destroy(self, _widget) -> None:
        Gtk.main_quit()

    def run(self) -> str | None:
        """Displays the window, runs the GTK main loop, and returns the validated key."""
        self.window.show_all()
        # Bring window to front
        self.window.present()
        self.entry.grab_focus()
        Gtk.main()
        return self.validated_key
