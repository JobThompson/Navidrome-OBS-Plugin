from __future__ import annotations

import os
from dataclasses import dataclass
from dataclasses import field
from pathlib import Path
from typing import Dict, Optional


def _as_int(value: Optional[str], default: int) -> int:
    if value is None:
        return default
    try:
        return int(str(value).strip())
    except ValueError:
        return default


def _as_float(value: Optional[str], default: float) -> float:
    if value is None:
        return default
    try:
        return float(str(value).strip())
    except ValueError:
        return default


def _clean_css_value(value: Optional[str], default: str) -> str:
    """Best-effort sanitation for values embedded into a <style> tag.

    We primarily strip newlines/control chars to avoid breaking CSS, while still
    allowing normal CSS tokens like rgba(...), #hex, and font-family lists.
    """

    if value is None:
        return default
    cleaned = str(value).replace("\r", " ").replace("\n", " ").strip()
    return cleaned or default


@dataclass(frozen=True)
class OverlayTheme:
    font_family: str = '"Segoe UI", sans-serif'
    text_color: str = "#f4f4f5"
    muted_opacity: float = 0.8

    card_bg: str = "rgba(10, 10, 10, 0.75)"
    card_radius_px: int = 14
    card_shadow: str = "0 8px 24px rgba(0, 0, 0, 0.45)"
    card_min_width_px: int = 320
    card_gap_px: int = 16
    card_padding_y_px: int = 16
    card_padding_x_px: int = 20

    cover_size_px: int = 96
    cover_radius_px: int = 12

    title_size_px: int = 18
    artist_size_px: int = 14
    time_size_px: int = 12

    progress_track_bg: str = "rgba(255, 255, 255, 0.2)"
    progress_height_px: int = 6
    accent_start: str = "#60a5fa"
    accent_end: str = "#34d399"

    def to_css_vars(self) -> Dict[str, str]:
        # Keep these stable; both HTML and /api/theme depend on the names.
        return {
            "--overlay-font-family": self.font_family,
            "--overlay-text-color": self.text_color,
            "--overlay-muted-opacity": str(self.muted_opacity),
            "--overlay-card-bg": self.card_bg,
            "--overlay-card-radius": f"{self.card_radius_px}px",
            "--overlay-card-shadow": self.card_shadow,
            "--overlay-card-min-width": f"{self.card_min_width_px}px",
            "--overlay-card-gap": f"{self.card_gap_px}px",
            "--overlay-card-padding-y": f"{self.card_padding_y_px}px",
            "--overlay-card-padding-x": f"{self.card_padding_x_px}px",
            "--overlay-cover-size": f"{self.cover_size_px}px",
            "--overlay-cover-radius": f"{self.cover_radius_px}px",
            "--overlay-title-size": f"{self.title_size_px}px",
            "--overlay-artist-size": f"{self.artist_size_px}px",
            "--overlay-time-size": f"{self.time_size_px}px",
            "--overlay-progress-track-bg": self.progress_track_bg,
            "--overlay-progress-height": f"{self.progress_height_px}px",
            "--overlay-accent-start": self.accent_start,
            "--overlay-accent-end": self.accent_end,
        }


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
    nothing_playing_placeholder: str
    theme: OverlayTheme = field(default_factory=OverlayTheme)


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
    "OVERLAY_NOTHING_PLAYING_PLACEHOLDER",

    # Theme (optional)
    "OVERLAY_THEME_FONT_FAMILY",
    "OVERLAY_THEME_TEXT_COLOR",
    "OVERLAY_THEME_MUTED_OPACITY",
    "OVERLAY_THEME_CARD_BG",
    "OVERLAY_THEME_CARD_RADIUS_PX",
    "OVERLAY_THEME_CARD_SHADOW",
    "OVERLAY_THEME_CARD_MIN_WIDTH_PX",
    "OVERLAY_THEME_CARD_GAP_PX",
    "OVERLAY_THEME_CARD_PADDING_Y_PX",
    "OVERLAY_THEME_CARD_PADDING_X_PX",
    "OVERLAY_THEME_COVER_SIZE_PX",
    "OVERLAY_THEME_COVER_RADIUS_PX",
    "OVERLAY_THEME_TITLE_SIZE_PX",
    "OVERLAY_THEME_ARTIST_SIZE_PX",
    "OVERLAY_THEME_TIME_SIZE_PX",
    "OVERLAY_THEME_PROGRESS_TRACK_BG",
    "OVERLAY_THEME_PROGRESS_HEIGHT_PX",
    "OVERLAY_THEME_ACCENT_START",
    "OVERLAY_THEME_ACCENT_END",
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

    nothing_playing_placeholder = (
        pick("OVERLAY_NOTHING_PLAYING_PLACEHOLDER", "dark") or "dark"
    ).strip().lower()
    if nothing_playing_placeholder in {"none", "off", "false", "0"}:
        nothing_playing_placeholder = "off"
    elif nothing_playing_placeholder not in {"dark", "light", "off"}:
        nothing_playing_placeholder = "dark"

    theme = OverlayTheme(
        font_family=_clean_css_value(pick("OVERLAY_THEME_FONT_FAMILY"), OverlayTheme().font_family),
        text_color=_clean_css_value(pick("OVERLAY_THEME_TEXT_COLOR"), OverlayTheme().text_color),
        muted_opacity=_as_float(pick("OVERLAY_THEME_MUTED_OPACITY"), OverlayTheme().muted_opacity),
        card_bg=_clean_css_value(pick("OVERLAY_THEME_CARD_BG"), OverlayTheme().card_bg),
        card_radius_px=_as_int(pick("OVERLAY_THEME_CARD_RADIUS_PX"), OverlayTheme().card_radius_px),
        card_shadow=_clean_css_value(pick("OVERLAY_THEME_CARD_SHADOW"), OverlayTheme().card_shadow),
        card_min_width_px=_as_int(
            pick("OVERLAY_THEME_CARD_MIN_WIDTH_PX"), OverlayTheme().card_min_width_px
        ),
        card_gap_px=_as_int(pick("OVERLAY_THEME_CARD_GAP_PX"), OverlayTheme().card_gap_px),
        card_padding_y_px=_as_int(
            pick("OVERLAY_THEME_CARD_PADDING_Y_PX"), OverlayTheme().card_padding_y_px
        ),
        card_padding_x_px=_as_int(
            pick("OVERLAY_THEME_CARD_PADDING_X_PX"), OverlayTheme().card_padding_x_px
        ),
        cover_size_px=_as_int(pick("OVERLAY_THEME_COVER_SIZE_PX"), OverlayTheme().cover_size_px),
        cover_radius_px=_as_int(
            pick("OVERLAY_THEME_COVER_RADIUS_PX"), OverlayTheme().cover_radius_px
        ),
        title_size_px=_as_int(pick("OVERLAY_THEME_TITLE_SIZE_PX"), OverlayTheme().title_size_px),
        artist_size_px=_as_int(
            pick("OVERLAY_THEME_ARTIST_SIZE_PX"), OverlayTheme().artist_size_px
        ),
        time_size_px=_as_int(pick("OVERLAY_THEME_TIME_SIZE_PX"), OverlayTheme().time_size_px),
        progress_track_bg=_clean_css_value(
            pick("OVERLAY_THEME_PROGRESS_TRACK_BG"), OverlayTheme().progress_track_bg
        ),
        progress_height_px=_as_int(
            pick("OVERLAY_THEME_PROGRESS_HEIGHT_PX"), OverlayTheme().progress_height_px
        ),
        accent_start=_clean_css_value(pick("OVERLAY_THEME_ACCENT_START"), OverlayTheme().accent_start),
        accent_end=_clean_css_value(pick("OVERLAY_THEME_ACCENT_END"), OverlayTheme().accent_end),
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
        nothing_playing_placeholder=nothing_playing_placeholder,
        theme=theme,
    )
