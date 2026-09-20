"""Command-line argument parsing and configuration options."""

import argparse


def parse_arguments(args: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments for Nexus Mods AutoInstaller."""
    parser = argparse.ArgumentParser(
        prog="nexus-autoinstaller",
        description="Official-compliant, concurrent, dependency-aware mod installer for Nexus Mods.",
    )

    # Optional subcommands / positional modes
    parser.add_argument(
        "subcommand",
        nargs="?",
        choices=["tabs", "scan", "cache", "local", "nexus"],
        help="Shortcut command: 'tabs' (browser tabs), 'local' (local mods/ folder), 'scan' (filesystem scan), 'cache', or 'nexus'.",
    )
    parser.add_argument(
        "action",
        nargs="?",
        default="",
        help="Sub-action: for 'cache' ('status', 'clean'), for 'nexus' ('tabs', 'file', 'url').",
    )
    parser.add_argument(
        "--yes", "-y",
        action="store_true",
        help="Skip interactive confirmation prompts and proceed automatically.",
    )


    # Ingestion Sources
    parser.add_argument(
        "--file", "-f",
        type=str,
        help="Path to text file containing Nexus Mods URLs (e.g. mods.txt).",
    )
    parser.add_argument(
        "--urls", "-u",
        nargs="+",
        help="One or more Nexus Mods URLs passed directly via command line.",
    )
    parser.add_argument(
        "--collect-tabs", "-c",
        action="store_true",
        help="Automatically collect open Nexus Mods tabs from browser via Chromium DevTools Protocol (port 9222).",
    )
    parser.add_argument(
        "--cdp-url",
        type=str,
        default="http://127.0.0.1:9222",
        help="Chromium DevTools Protocol endpoint (default: http://127.0.0.1:9222).",
    )

    # Execution Modes
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate the installation plan, dependency tree, and requirements without downloading or writing files.",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume previously interrupted download and installation operations.",
    )
    parser.add_argument(
        "--scan",
        action="store_true",
        help="Scan local mods directory to catalog pre-existing unmanaged files.",
    )
    parser.add_argument(
        "--repair",
        type=int,
        metavar="MOD_ID",
        help="Verify files on disk against database manifest for the specified mod ID and report discrepancies.",
    )
    parser.add_argument(
        "--check-updates",
        action="store_true",
        help="Check if installed mods have newer versions available on Nexus Mods.",
    )
    parser.add_argument(
        "--single-mod",
        type=int,
        metavar="MOD_ID",
        help="Target only a specific mod ID for safe single-mod validation (e.g. 868).",
    )
    parser.add_argument(
        "--test-onboarding-ui",
        action="store_true",
        help="Launch the graphical onboarding window in diagnostic mode to test keyboard, paste, and visibility controls.",
    )

    # Game Configuration & Target
    parser.add_argument(
        "--game-dir",
        type=str,
        help="Target game installation directory.",
    )
    parser.add_argument(
        "--profile",
        type=str,
        help="Game profile to use (e.g. mysummercar, skyrimspecialedition, generic).",
    )
    parser.add_argument(
        "--api-key",
        type=str,
        help=argparse.SUPPRESS,  # Deprecated and insecure; use interactive onboarding instead
    )
    parser.add_argument(
        "--config",
        type=str,
        default="config.json",
        help="Path to JSON configuration file (default: config.json).",
    )
    parser.add_argument(
        "--max-downloads",
        type=int,
        default=4,
        help="Maximum concurrent downloads (default: 4).",
    )

    return parser.parse_args(args)
