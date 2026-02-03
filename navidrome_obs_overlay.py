#!/usr/bin/env python3
"""Serve a small OBS-friendly overlay for Navidrome's now-playing data."""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Optional
from urllib import parse, request


@dataclass(frozen=True)
class OverlayConfig:
    """Container for Navidrome and server configuration values.

    Each field mirrors a setting supplied through environment variables or the
    optional .env file, keeping configuration in a single structured object.
    """

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


def load_env_file(env_path: Path) -> Dict[str, str]:
    """Read a .env file and return any key/value pairs it defines.

    The loader ignores comments and blank lines so the overlay can rely on
    a simple KEY=VALUE format without additional parsing dependencies.
    """

    env_values: Dict[str, str] = {}
    if not env_path.exists():
        return env_values

    # Read each line so we can gracefully ignore comments and blank lines.
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


def load_config() -> OverlayConfig:
    """Load configuration from environment variables or the local .env file.

    Environment variables take precedence, but a colocated .env file can be
    used for local development so credentials stay out of source control.
    """

    env_path = Path(__file__).with_name(".env")
    file_values = load_env_file(env_path)

    # Prefer actual environment variables, but fall back to .env file values.
    def pick(name: str, default: Optional[str] = None) -> Optional[str]:
        return os.environ.get(name, file_values.get(name, default))

    navidrome_url = (pick("NAVIDROME_URL") or "").rstrip("/")
    navidrome_user = pick("NAVIDROME_USER") or ""
    navidrome_password = pick("NAVIDROME_PASSWORD") or ""

    if not navidrome_url or not navidrome_user or not navidrome_password:
        raise ValueError(
            "NAVIDROME_URL, NAVIDROME_USER, and NAVIDROME_PASSWORD must be set."
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
        refresh_seconds=int(pick("OVERLAY_REFRESH_SECONDS", "3")),
        show_progress=pick("OVERLAY_SHOW_PROGRESS", "true").lower() in ("true", "1", "yes"),
    )


def build_subsonic_url(
    config: OverlayConfig, endpoint: str, params: Dict[str, Any], include_format: bool = True
) -> str:
    """Build a complete Subsonic-compatible API URL for Navidrome.

    The helper injects the shared authentication parameters and appends any
    endpoint-specific query values so callers only pass what is unique.
    """

    # The Subsonic API expects these standard parameters on every call.
    base_params: Dict[str, Any] = {
        "u": config.navidrome_user,
        "p": config.navidrome_password,
        "v": config.navidrome_version,
        "c": config.navidrome_client,
    }
    if include_format:
        base_params["f"] = "json"

    base_params.update(params)
    query_string = parse.urlencode(base_params)
    return f"{config.navidrome_url}/rest/{endpoint}.view?{query_string}"


def fetch_json(url: str, timeout: float) -> Dict[str, Any]:
    """Retrieve JSON data from the given URL and decode the response.

    This wrapper keeps networking logic centralized so request headers and
    timeout handling remain consistent for each Navidrome API call.
    """

    request_obj = request.Request(url, headers={"User-Agent": "Navidrome-OBS-Overlay"})
    with request.urlopen(request_obj, timeout=timeout) as response:
        payload = response.read().decode("utf-8")
    return json.loads(payload)


def fetch_now_playing(config: OverlayConfig) -> Optional[Dict[str, Any]]:
    """Call Navidrome's getNowPlaying endpoint and return the first entry.

    The Subsonic API can return a single object or a list depending on how many
    tracks are playing, so the function normalizes the output to one dict.
    """

    url = build_subsonic_url(config, "getNowPlaying", {})
    response = fetch_json(url, config.request_timeout)
    subsonic_response = response.get("subsonic-response", {})
    if subsonic_response.get("status") != "ok":
        return None

    now_playing = subsonic_response.get("nowPlaying", {})
    entries = now_playing.get("entry")
    if not entries:
        return None

    # The Subsonic API may return a list or a single dict depending on count.
    if isinstance(entries, list):
        return entries[0]
    return entries


def build_now_playing_payload(
    _config: OverlayConfig, entry: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    """Normalize now-playing data into a client-friendly payload.

    The overlay UI uses this standardized structure to display titles, cover
    art, and progress without needing to understand Subsonic response shapes.
    """

    server_time = time.time()
    if not entry:
        return {
            "isPlaying": False,
            "serverTime": server_time,
        }

    duration = int(entry.get("duration") or 0)
    elapsed_minutes = float(entry.get("minutesAgo") or 0)
    raw_elapsed_seconds = max(0, int(elapsed_minutes * 60))
    elapsed_seconds = (
        min(raw_elapsed_seconds, duration) if duration else raw_elapsed_seconds
    )

    cover_id = entry.get("coverArt") or entry.get("id") or ""
    cover_url = f"/api/cover/{parse.quote(str(cover_id))}" if cover_id else ""

    return {
        "isPlaying": True,
        "title": entry.get("title") or "Unknown Title",
        "artist": entry.get("artist") or "Unknown Artist",
        "album": entry.get("album") or "",
        "coverUrl": cover_url,
        "durationSeconds": duration,
        "elapsedSeconds": elapsed_seconds,
        "serverTime": server_time,
    }


def fetch_cover_art(config: OverlayConfig, cover_id: str) -> Optional[bytes]:
    """Download cover art bytes for the provided cover ID.

    Cover art is proxied through this server so Navidrome credentials remain on
    the backend instead of being exposed to the browser source in OBS.
    """

    url = build_subsonic_url(
        config, "getCoverArt", {"id": cover_id}, include_format=False
    )
    request_obj = request.Request(url, headers={"User-Agent": "Navidrome-OBS-Overlay"})
    with request.urlopen(request_obj, timeout=config.request_timeout) as response:
        return response.read()


def send_json(handler: BaseHTTPRequestHandler, payload: Dict[str, Any]) -> None:
    """Send a JSON response with cache-busting headers.

    The helper writes consistent headers so the OBS browser source always
    retrieves fresh now-playing data on each refresh interval.
    """

    encoded = json.dumps(payload).encode("utf-8")
    handler.send_response(HTTPStatus.OK)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(encoded)))
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()
    handler.wfile.write(encoded)


def send_bytes(
    handler: BaseHTTPRequestHandler, data: bytes, content_type: str
) -> None:
    """Send a binary response, typically used for cover art.

    This keeps response handling uniform for images and other binary payloads
    while still disabling browser caching.
    """

    handler.send_response(HTTPStatus.OK)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Content-Length", str(len(data)))
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()
    handler.wfile.write(data)


def render_index(refresh_seconds: int, show_progress: bool = True) -> bytes:
    """Create the HTML for the overlay page.

    The returned markup includes the CSS styling and JavaScript polling logic
    needed for OBS to show an always-updated now-playing panel.
    """

    # Build progress elements conditionally
    progress_html = ""
    if show_progress:
        progress_html = '''
      <div class="progress-track" id="progress-track">
        <div class="progress-fill" id="progress"></div>
      </div>
      <div class="time" id="time"></div>'''

    # Build progress JavaScript variables conditionally
    progress_js_vars = ""
    if show_progress:
        progress_js_vars = '''
    const progressEl = document.getElementById("progress");
    const timeEl = document.getElementById("time");'''

    # Build progress JavaScript functions conditionally
    progress_js_functions = ""
    if show_progress:
        progress_js_functions = '''
    function formatTime(totalSeconds) {
      const minutes = Math.floor(totalSeconds / 60);
      const seconds = Math.floor(totalSeconds % 60).toString().padStart(2, "0");
      return `${minutes}:${seconds}`;
    }

    function updateProgress() {
      if (!currentPayload || !currentPayload.isPlaying) {
        return;
      }
      const now = Date.now() / 1000;
      const duration = currentPayload.durationSeconds || 0;
      const elapsed = Math.min(
        duration,
        (currentPayload.elapsedSeconds || 0) + (now - currentPayload.serverTime)
      );
      const percent = duration > 0 ? (elapsed / duration) * 100 : 0;
      progressEl.style.width = `${percent}%`;
      timeEl.textContent = duration ? `${formatTime(elapsed)} / ${formatTime(duration)}` : "";
    }'''

    progress_update_call = ""
    if show_progress:
        progress_update_call = '''
      updateProgress();'''

    progress_interval = ""
    if show_progress:
        progress_interval = '''
    setInterval(updateProgress, 500);'''

    progress_reset = ""
    if show_progress:
        progress_reset = '''
        progressEl.style.width = "0%";
        timeEl.textContent = "";'''

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Navidrome Now Playing</title>
  <style>
    :root {{
      color-scheme: dark;
    }}
    body {{
      margin: 0;
      font-family: "Segoe UI", sans-serif;
      background: transparent;
      color: #f4f4f5;
    }}
    .card {{
      display: flex;
      align-items: center;
      gap: 16px;
      padding: 16px 20px;
      background: rgba(10, 10, 10, 0.75);
      border-radius: 14px;
      width: fit-content;
      min-width: 320px;
      box-shadow: 0 8px 24px rgba(0, 0, 0, 0.45);
    }}
    .cover {{
      width: 96px;
      height: 96px;
      border-radius: 12px;
      object-fit: cover;
      background: rgba(255, 255, 255, 0.08);
      position: relative;
    }}
    .cover.default::before {{
      content: "\\1F3B5";
      position: absolute;
      top: 50%;
      left: 50%;
      transform: translate(-50%, -50%);
      font-size: 32px;
      opacity: 0.6;
    }}
    .info {{
      display: flex;
      flex-direction: column;
      min-width: 180px;
    }}
    .title {{
      font-size: 18px;
      font-weight: 600;
    }}
    .artist {{
      font-size: 14px;
      opacity: 0.8;
      margin-top: 4px;
    }}
    .progress-track {{
      position: relative;
      height: 6px;
      border-radius: 999px;
      background: rgba(255, 255, 255, 0.2);
      margin-top: 12px;
      overflow: hidden;
    }}
    .progress-fill {{
      position: absolute;
      height: 100%;
      left: 0;
      top: 0;
      background: linear-gradient(90deg, #60a5fa, #34d399);
      width: 0%;
      transition: width 0.4s ease;
    }}
    .time {{
      font-size: 12px;
      margin-top: 8px;
      opacity: 0.75;
    }}
  </style>
</head>
<body>
  <div class="card">
    <img class="cover" id="cover" alt="Cover art" />
    <div class="info">
      <div class="title" id="title">Loading…</div>
      <div class="artist" id="artist"></div>{progress_html}
    </div>
  </div>

  <script>
    const refreshMs = {refresh_seconds * 1000};
    const titleEl = document.getElementById("title");
    const artistEl = document.getElementById("artist");
    const coverEl = document.getElementById("cover");{progress_js_vars}
    let currentPayload = null;{progress_js_functions}

    function applyPayload(payload) {{
      currentPayload = payload;
      if (!payload.isPlaying) {{
        titleEl.textContent = "Nothing playing";
        artistEl.textContent = "";
        coverEl.removeAttribute("src");
        coverEl.classList.add("default");{progress_reset}
        return;
      }}

      titleEl.textContent = payload.title;
      artistEl.textContent = payload.artist || "";
      if (payload.coverUrl) {{
        coverEl.src = payload.coverUrl;
        coverEl.classList.remove("default");
      }} else {{
        coverEl.removeAttribute("src");
        coverEl.classList.add("default");
      }}{progress_update_call}
    }}

    async function refreshNowPlaying() {{
      try {{
        const response = await fetch("/api/now-playing", {{ cache: "no-store" }});
        const payload = await response.json();
        applyPayload(payload);
      }} catch (error) {{
        titleEl.textContent = "Unable to reach Navidrome";
        artistEl.textContent = "";
        coverEl.removeAttribute("src");
        coverEl.classList.add("default");{progress_reset}
      }}
    }}

    refreshNowPlaying();
    setInterval(refreshNowPlaying, refreshMs);{progress_interval}
  </script>
</body>
</html>
"""
    return html.encode("utf-8")


class NavidromeOverlayHandler(BaseHTTPRequestHandler):
    """HTTP handler that serves the overlay page and API endpoints.

    The handler dispatches requests between the HTML overlay, JSON API data,
    and the image proxy endpoint for cover art.
    """

    config: OverlayConfig

    def do_GET(self) -> None:  # noqa: N802
        """Route GET requests to the overlay HTML or JSON endpoints.

        This method inspects the request path and forwards handling to the
        corresponding helper so each endpoint stays focused.
        """

        parsed = parse.urlparse(self.path)

        if parsed.path in {"/", "/index.html"}:
            self._handle_index()
            return

        if parsed.path == "/api/now-playing":
            self._handle_now_playing()
            return

        if parsed.path.startswith("/api/cover/"):
            cover_id = parsed.path.split("/api/cover/", 1)[1]
            self._handle_cover_art(cover_id)
            return

        self.send_error(HTTPStatus.NOT_FOUND, "Endpoint not found")

    def _handle_index(self) -> None:
        """Serve the overlay HTML with the configured refresh interval.

        The HTML is generated at request time so the refresh interval can be
        adjusted through configuration without editing the template.
        """

        html_bytes = render_index(self.config.refresh_seconds, self.config.show_progress)
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(html_bytes)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(html_bytes)

    def _handle_now_playing(self) -> None:
        """Fetch Navidrome data and return normalized now-playing JSON.

        Any API errors are caught and returned as a safe payload so the overlay
        can display a friendly status instead of crashing.
        """

        try:
            entry = fetch_now_playing(self.config)
            payload = build_now_playing_payload(self.config, entry)
        except Exception as exc:  # pylint: disable=broad-except
            print(f"Failed to fetch now playing: {exc}")
            payload = {
                "isPlaying": False,
                "serverTime": time.time(),
                "error": f"Unable to reach Navidrome ({type(exc).__name__})",
            }

        send_json(self, payload)

    def _handle_cover_art(self, cover_id: str) -> None:
        """Proxy Navidrome cover art so credentials stay server-side.

        The endpoint validates the requested cover ID and forwards errors to
        the client when the Navidrome instance cannot return artwork.
        """

        if not cover_id:
            self.send_error(HTTPStatus.BAD_REQUEST, "Cover art ID missing")
            return

        try:
            cover_bytes = fetch_cover_art(self.config, cover_id)
        except Exception as exc:  # pylint: disable=broad-except
            print(f"Failed to fetch cover art: {exc}")
            self.send_error(
                HTTPStatus.BAD_GATEWAY,
                f"Unable to fetch cover art ({type(exc).__name__})",
            )
            return

        if not cover_bytes:
            self.send_error(HTTPStatus.NOT_FOUND, "Cover art unavailable")
            return

        send_bytes(self, cover_bytes, "image/jpeg")


def build_handler(config: OverlayConfig) -> type[NavidromeOverlayHandler]:
    """Create a request handler class bound to the provided configuration.

    Binding the configuration on the class keeps per-request logic simple and
    avoids reliance on global variables for settings.
    """

    class BoundHandler(NavidromeOverlayHandler):
        """Handler subclass that carries the overlay configuration."""

    BoundHandler.config = config
    return BoundHandler


def run_server(config: OverlayConfig) -> None:
    """Start the HTTP server loop for the overlay.

    This function instantiates the threaded HTTP server and blocks forever so
    the overlay can be left running while OBS is open.
    """

    handler = build_handler(config)
    server = ThreadingHTTPServer((config.server_host, config.server_port), handler)
    print(
        f"Overlay running on http://{config.server_host}:{config.server_port} (refresh {config.refresh_seconds}s)"
    )
    server.serve_forever()


def main() -> None:
    """Entry point that loads configuration and launches the server.

    Keeping startup logic here allows the module to be imported without side
    effects, while still supporting `python navidrome_obs_overlay.py`.
    """

    config = load_config()
    run_server(config)


if __name__ == "__main__":
    main()
