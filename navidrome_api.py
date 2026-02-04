from __future__ import annotations

import json
import time
from typing import Any, Dict, Optional
from urllib import parse, request

from overlay_config import OverlayConfig


DEFAULT_API_VERSION_CANDIDATES: tuple[str, ...] = (
    "1.16.1",
    "1.16.0",
    "1.15.0",
    "1.14.0",
    "1.13.0",
    "1.12.0",
)


def build_subsonic_url(
    config: OverlayConfig, endpoint: str, params: Dict[str, Any], include_format: bool = True
) -> str:
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
    request_obj = request.Request(url, headers={"User-Agent": "Navidrome-OBS-Overlay"})
    with request.urlopen(request_obj, timeout=timeout) as response:
        payload = response.read().decode("utf-8")
    return json.loads(payload)


def detect_subsonic_api_version(
    *,
    navidrome_url: str,
    navidrome_user: str,
    navidrome_password: str,
    navidrome_client: str = "obs-overlay",
    timeout: float = 6.0,
    candidates: tuple[str, ...] = DEFAULT_API_VERSION_CANDIDATES,
) -> str:
    """Detect the REST protocol version supported by the server.

    Subsonic-compatible servers (including Navidrome) typically expose this on
    /rest/ping.view by returning JSON like:
      {"subsonic-response": {"status": "ok", "version": "1.16.1", ...}}

    The API requires a 'v' parameter, so we try a few common versions until the
    server responds successfully.
    """

    base_url = navidrome_url.rstrip("/")
    for version in candidates:
        params: Dict[str, Any] = {
            "u": navidrome_user,
            "p": navidrome_password,
            "v": version,
            "c": navidrome_client,
            "f": "json",
        }
        url = f"{base_url}/rest/ping.view?{parse.urlencode(params)}"

        response = fetch_json(url, timeout)
        subsonic_response = response.get("subsonic-response", {})
        status = subsonic_response.get("status")

        if status == "ok":
            detected = subsonic_response.get("version")
            return str(detected or version)

        error = subsonic_response.get("error") or {}
        code = str(error.get("code") or "")
        message = str(error.get("message") or "").strip()

        # Common Subsonic error codes (varies by server, but these are typical):
        # 20: Incompatible protocol version
        # 30: Wrong username or password
        if code == "20":
            continue
        if code == "30":
            raise ValueError("Authentication failed: wrong username or password")

        # If we get here, it's probably not version-related.
        details = f" (code {code})" if code else ""
        raise ValueError(f"Ping failed{details}: {message or 'unknown error'}")

    raise ValueError(
        "Could not auto-detect a compatible API version. "
        "Try setting the API version manually (Navidrome usually supports 1.16.1)."
    )


def fetch_now_playing(config: OverlayConfig) -> Optional[Dict[str, Any]]:
    entries = fetch_now_playing_entries(config)
    return entries[0] if entries else None


def fetch_now_playing_entries(config: OverlayConfig) -> list[Dict[str, Any]]:
    """Fetch all now-playing entries.

    getNowPlaying can return multiple entries (across devices/users). The overlay
    historically used the first entry, but some logic benefits from seeing the
    whole list.
    """

    url = build_subsonic_url(config, "getNowPlaying", {})
    response = fetch_json(url, config.request_timeout)
    subsonic_response = response.get("subsonic-response", {})
    if subsonic_response.get("status") != "ok":
        return []

    now_playing = subsonic_response.get("nowPlaying", {})
    entries = now_playing.get("entry")
    if not entries:
        return []

    if isinstance(entries, list):
        return [e for e in entries if isinstance(e, dict)]
    if isinstance(entries, dict):
        return [entries]
    return []


def fetch_play_queue_current(
    config: OverlayConfig,
) -> tuple[Optional[Dict[str, Any]], Optional[int]]:
    """Fetch the current track from the Subsonic play queue.

    This is useful when playback is paused: some clients/servers may not report
    anything in getNowPlaying while paused, but the play queue still knows the
    current track.

    Returns (entry, positionSeconds) where positionSeconds may be None.
    """

    url = build_subsonic_url(config, "getPlayQueue", {})
    response = fetch_json(url, config.request_timeout)
    subsonic_response = response.get("subsonic-response", {})
    if subsonic_response.get("status") != "ok":
        return (None, None)

    play_queue = subsonic_response.get("playQueue") or {}
    current_id = str(play_queue.get("current") or "")
    position_raw = play_queue.get("position")
    position_seconds: Optional[int]
    try:
        position_seconds = int(position_raw) if position_raw is not None else None
    except (TypeError, ValueError):
        position_seconds = None

    entries = play_queue.get("entry")
    if not entries:
        return (None, position_seconds)

    entry_list: list[Dict[str, Any]]
    if isinstance(entries, list):
        entry_list = [e for e in entries if isinstance(e, dict)]
    elif isinstance(entries, dict):
        entry_list = [entries]
    else:
        entry_list = []

    if not entry_list:
        return (None, position_seconds)

    if current_id:
        for entry in entry_list:
            if str(entry.get("id") or "") == current_id:
                return (entry, position_seconds)

    return (entry_list[0], position_seconds)


def build_now_playing_payload(
    _config: OverlayConfig,
    entry: Optional[Dict[str, Any]],
    *,
    is_paused: bool = False,
    elapsed_seconds_override: Optional[int] = None,
) -> Dict[str, Any]:
    server_time = time.time()
    if not entry:
        return {
            "isPlaying": False,
            "serverTime": server_time,
        }

    duration = int(entry.get("duration") or 0)
    if elapsed_seconds_override is not None:
        raw_elapsed_seconds = max(0, int(elapsed_seconds_override))
        elapsed_seconds = min(raw_elapsed_seconds, duration) if duration else raw_elapsed_seconds
    else:
        elapsed_minutes = float(entry.get("minutesAgo") or 0)
        raw_elapsed_seconds = max(0, int(elapsed_minutes * 60))
        elapsed_seconds = min(raw_elapsed_seconds, duration) if duration else raw_elapsed_seconds

    cover_id = entry.get("coverArt") or entry.get("id") or ""
    cover_url = f"/api/cover/{parse.quote(str(cover_id))}" if cover_id else ""

    return {
        "isPlaying": True,
        "isPaused": bool(is_paused),
        "title": entry.get("title") or "Unknown Title",
        "artist": entry.get("artist") or "Unknown Artist",
        "album": entry.get("album") or "",
        "coverUrl": cover_url,
        "durationSeconds": duration,
        "elapsedSeconds": elapsed_seconds,
        "serverTime": server_time,
    }


def fetch_cover_art(config: OverlayConfig, cover_id: str) -> Optional[bytes]:
    url = build_subsonic_url(config, "getCoverArt", {"id": cover_id}, include_format=False)
    request_obj = request.Request(url, headers={"User-Agent": "Navidrome-OBS-Overlay"})
    with request.urlopen(request_obj, timeout=config.request_timeout) as response:
        return response.read()
