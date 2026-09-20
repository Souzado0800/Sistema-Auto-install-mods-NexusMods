"""
Component: Toast Helper.
Non-intrusive internal toast notification utility using Adw.ToastOverlay.
"""

from __future__ import annotations

import gi
gi.require_version("Adw", "1")
from gi.repository import Adw


class ToastService:
    """Singleton service to post non-blocking in-app toasts across views."""

    _overlay: Adw.ToastOverlay | None = None

    @classmethod
    def register_overlay(cls, overlay: Adw.ToastOverlay) -> None:
        cls._overlay = overlay

    @classmethod
    def show(cls, title: str, timeout_seconds: int = 3) -> None:
        if cls._overlay is not None:
            toast = Adw.Toast.new(title)
            toast.set_timeout(timeout_seconds)
            cls._overlay.add_toast(toast)
