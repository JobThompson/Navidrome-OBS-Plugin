from __future__ import annotations

import json
import sys
import threading
import time
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Dict
from urllib import parse

from navidrome_api import (
    build_now_playing_payload,
    fetch_cover_art,
    fetch_now_playing,
)
from overlay_config import OverlayConfig
from overlay_html import render_index


def _guess_content_type(path: str) -> str:
    lowered = path.lower()
    if lowered.endswith(".png"):
        return "image/png"
    if lowered.endswith(".jpg") or lowered.endswith(".jpeg"):
        return "image/jpeg"
    if lowered.endswith(".gif"):
        return "image/gif"
    if lowered.endswith(".webp"):
        return "image/webp"
    return "application/octet-stream"


def send_json(handler: BaseHTTPRequestHandler, payload: Dict) -> None:
    encoded = json.dumps(payload).encode("utf-8")
    handler.send_response(HTTPStatus.OK)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(encoded)))
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()
    handler.wfile.write(encoded)


def send_bytes(handler: BaseHTTPRequestHandler, data: bytes, content_type: str) -> None:
    handler.send_response(HTTPStatus.OK)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Content-Length", str(len(data)))
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()
    handler.wfile.write(data)


class NavidromeOverlayHandler(BaseHTTPRequestHandler):
    config: OverlayConfig

    def do_GET(self) -> None:  # noqa: N802
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

        if parsed.path.startswith("/assets/"):
            asset_path = parsed.path.split("/assets/", 1)[1]
            self._handle_asset(asset_path)
            return

        self.send_error(HTTPStatus.NOT_FOUND, "Endpoint not found")

    def _handle_index(self) -> None:
        placeholder_url = ""
        if self.config.nothing_playing_placeholder == "dark":
            placeholder_url = "/assets/" + parse.quote("Nothing Playing Dark.png")
        elif self.config.nothing_playing_placeholder == "light":
            placeholder_url = "/assets/" + parse.quote("Nothing Playing Light.png")

        html_bytes = render_index(
            self.config.refresh_seconds,
            self.config.show_progress,
            theme_css_vars=self.config.theme.to_css_vars(),
            nothing_playing_cover_url=placeholder_url or None,
        )
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(html_bytes)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(html_bytes)

    def _handle_asset(self, asset_path: str) -> None:
        # Prevent traversal; only allow files under ./assets.
        assets_root = Path(__file__).with_name("assets")
        requested = parse.unquote(asset_path).lstrip("/\\")
        candidate = (assets_root / requested).resolve()
        try:
            assets_root_resolved = assets_root.resolve()
        except FileNotFoundError:
            assets_root_resolved = assets_root

        if assets_root_resolved not in candidate.parents and candidate != assets_root_resolved:
            self.send_error(HTTPStatus.BAD_REQUEST, "Invalid asset path")
            return

        if not candidate.exists() or not candidate.is_file():
            self.send_error(HTTPStatus.NOT_FOUND, "Asset not found")
            return

        data = candidate.read_bytes()
        send_bytes(self, data, _guess_content_type(candidate.name))

    def _handle_now_playing(self) -> None:
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
    class BoundHandler(NavidromeOverlayHandler):
        pass

    BoundHandler.config = config
    return BoundHandler


def run_server(config: OverlayConfig, open_browser: bool = False) -> None:
    handler = build_handler(config)
    try:
        server = ThreadingHTTPServer((config.server_host, config.server_port), handler)
    except OSError as exc:
        print(
            f"Unable to start server on {config.server_host}:{config.server_port} ({exc}).",
            file=sys.stderr,
        )
        print(
            "Tip: Another app may be using that port. Update OVERLAY_PORT in .env or rerun setup.",
            file=sys.stderr,
        )
        raise

    overlay_url = f"http://{config.server_host}:{config.server_port}"
    print(f"Overlay running: {overlay_url} (refresh {config.refresh_seconds}s)")
    print(f"OBS Browser Source URL: {overlay_url}")

    if open_browser:
        threading.Timer(0.6, lambda: webbrowser.open(overlay_url)).start()

    server.serve_forever()
