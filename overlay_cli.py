from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Dict, Optional

from overlay_config import load_config
from overlay_server import run_server
from setup_wizard import (
    is_interactive,
    run_cli_setup,
    run_gui_setup,
    tkinter_available,
)


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Serve an OBS-friendly now-playing overlay for Navidrome.",
    )
    parser.add_argument(
        "--setup",
        action="store_true",
        help="Run guided setup (CLI) to create/update .env",
    )
    parser.add_argument("--gui", action="store_true", help="Run GUI setup (if available)")
    parser.add_argument(
        "--setup-only",
        action="store_true",
        help="Exit after setup instead of starting the server",
    )
    parser.add_argument(
        "--open",
        action="store_true",
        help="Open the overlay page in your default browser after starting",
    )
    parser.add_argument(
        "--env-file",
        default=None,
        help="Path to a .env file (defaults to .env next to this script)",
    )
    parser.add_argument("--host", default=None, help="Override overlay host (OVERLAY_HOST)")
    parser.add_argument(
        "--port", default=None, type=int, help="Override overlay port (OVERLAY_PORT)"
    )
    parser.add_argument(
        "--refresh",
        default=None,
        type=int,
        help="Override refresh interval seconds (OVERLAY_REFRESH_SECONDS)",
    )
    parser.add_argument(
        "--show-progress",
        dest="show_progress",
        action="store_true",
        help="Show progress bar + time",
    )
    parser.add_argument(
        "--hide-progress",
        dest="show_progress",
        action="store_false",
        help="Hide progress bar + time",
    )
    parser.set_defaults(show_progress=None)
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> None:
    args = parse_args(argv)

    env_path = Path(args.env_file) if args.env_file else Path(__file__).with_name(".env")

    if args.gui:
        if not tkinter_available():
            print("GUI setup is unavailable on this Python install; using the CLI setup instead.\n")
            run_cli_setup(env_path)
            if args.setup_only:
                return
        else:
            start = run_gui_setup(env_path)
            if start is None and args.setup_only:
                return
            if args.setup_only and start is False:
                return

    if args.setup and not args.gui:
        run_cli_setup(env_path)
        if args.setup_only:
            return

    overrides: Dict[str, str] = {}
    if args.host:
        overrides["OVERLAY_HOST"] = args.host
    if args.port is not None:
        overrides["OVERLAY_PORT"] = str(args.port)
    if args.refresh is not None:
        overrides["OVERLAY_REFRESH_SECONDS"] = str(args.refresh)
    if args.show_progress is not None:
        overrides["OVERLAY_SHOW_PROGRESS"] = "true" if args.show_progress else "false"

    try:
        config = load_config(env_path, overrides=overrides)
    except ValueError as exc:
        if is_interactive() and not args.setup_only and not args.gui:
            print(str(exc))
            print("\nStarting guided setup…\n")
            run_cli_setup(env_path)
            config = load_config(env_path, overrides=overrides)
        else:
            print(str(exc), file=sys.stderr)
            raise

    run_server(config, open_browser=args.open)
