from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional


@dataclass(frozen=True)
class OverlayConfig:
    navidrome_url: str
    navidrome_user: str
    navidrome_password: str
    navidrome_client: str
    navidrome_version: str
    request_timeout: float
    server_host: str
    server_port: int
    refresh_seconds: int
    show_progress: bool


ENV_KEY_ORDER: tuple[str, ...] = (
    "NAVIDROME_URL",
    "NAVIDROME_USER",
    "NAVIDROME_PASSWORD",
    "NAVIDROME_CLIENT_NAME",
    "NAVIDROME_API_VERSION",
    "NAVIDROME_TIMEOUT",
    "OVERLAY_HOST",
    "OVERLAY_PORT",
    "OVERLAY_REFRESH_SECONDS",
    "OVERLAY_SHOW_PROGRESS",
)


def load_env_file(env_path: Path) -> Dict[str, str]:
    env_values: Dict[str, str] = {}
    if not env_path.exists():
        return env_values

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        cleaned_value = value.strip().strip('"').strip("'")
        env_values[key.strip()] = cleaned_value

    return env_values


def write_env_file(env_path: Path, values: Dict[str, str]) -> None:
    lines: list[str] = [
        "# Navidrome OBS Overlay configuration",
        "# This file is automatically read by navidrome_obs_overlay.py",
        "#",
        "# Tip: .env is ignored by git via .gitignore (do not commit credentials)",
        "",
    ]

    for key in ENV_KEY_ORDER:
        if key in values:
            lines.append(f"{key}={values[key]}")
    for key in sorted(set(values) - set(ENV_KEY_ORDER)):
        lines.append(f"{key}={values[key]}")

    env_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def load_config(
    env_path: Optional[Path] = None, overrides: Optional[Dict[str, str]] = None
) -> OverlayConfig:
    env_path = env_path or Path(__file__).with_name(".env")
    file_values = load_env_file(env_path)
    overrides = overrides or {}

    def pick(name: str, default: Optional[str] = None) -> Optional[str]:
        if name in overrides and overrides[name] is not None:
            return overrides[name]
        return os.environ.get(name, file_values.get(name, default))

    navidrome_url = (pick("NAVIDROME_URL") or "").rstrip("/")
    navidrome_user = pick("NAVIDROME_USER") or ""
    navidrome_password = pick("NAVIDROME_PASSWORD") or ""

    if not navidrome_url or not navidrome_user or not navidrome_password:
        raise ValueError(
            "Missing configuration. Run the setup wizard with: python navidrome_obs_overlay.py --setup\n"
            "(or create a .env file next to this script)."
        )

    show_progress = (pick("OVERLAY_SHOW_PROGRESS", "false") or "false").lower() in (
        "true",
        "1",
        "yes",
    )

    return OverlayConfig(
        navidrome_url=navidrome_url,
        navidrome_user=navidrome_user,
        navidrome_password=navidrome_password,
        navidrome_client=pick("NAVIDROME_CLIENT_NAME", "obs-overlay"),
        navidrome_version=pick("NAVIDROME_API_VERSION", "1.16.1"),
        request_timeout=float(pick("NAVIDROME_TIMEOUT", "6")),
        server_host=pick("OVERLAY_HOST", "127.0.0.1"),
        server_port=int(pick("OVERLAY_PORT", "8080")),
        refresh_seconds=int(pick("OVERLAY_REFRESH_SECONDS", "1")),
        show_progress=show_progress,
    )
