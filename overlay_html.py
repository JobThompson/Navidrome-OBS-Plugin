from __future__ import annotations

from typing import Dict, Optional


def _css_vars_block(css_vars: Optional[Dict[str, str]]) -> str:
    if not css_vars:
        return ""

    lines: list[str] = []
    for key, value in css_vars.items():
        # Keys are controlled by our code; values come from config/env.
        safe_value = str(value).replace("\r", " ").replace("\n", " ").strip()
        lines.append(f"      {key}: {safe_value};")
    return "\n".join(lines)


def render_index(
    refresh_seconds: int,
    show_progress: bool = True,
    theme_css_vars: Optional[Dict[str, str]] = None,
    nothing_playing_cover_url: Optional[str] = None,
) -> bytes:
    progress_html = ""
    if show_progress:
        progress_html = '''
      <div class="progress-track" id="progress-track">
        <div class="progress-fill" id="progress"></div>
      </div>
      <div class="time" id="time"></div>'''

    progress_js_vars = ""
    if show_progress:
        progress_js_vars = '''
    const progressEl = document.getElementById("progress");
    const timeEl = document.getElementById("time");'''

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
      const baseElapsed = currentPayload.elapsedSeconds || 0;
      let elapsed = baseElapsed;
      if (!currentPayload.isPaused) {
        // If the overlay/tab was throttled/suspended (OBS, background, system sleep),
        // the payload can become very stale. Avoid jumping the progress to 100% and
        // trigger a refresh to recover quickly.
        const driftSeconds = now - (currentPayload.serverTime || 0);
        const maxDriftSeconds = Math.max(2, (refreshMs / 1000) * 2);
        if (driftSeconds > maxDriftSeconds) {
          // Fire-and-forget; refreshNowPlaying is defined below.
          refreshNowPlaying();
        }
        const safeDriftSeconds = Math.min(Math.max(driftSeconds, 0), maxDriftSeconds);
        elapsed = Math.min(duration, baseElapsed + safeDriftSeconds);
      }
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

    theme_vars = _css_vars_block(theme_css_vars)

    placeholder_cover = (nothing_playing_cover_url or "").replace("\r", "").replace("\n", "")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Navidrome Now Playing</title>
  <style>
    :root {{
      color-scheme: dark;
      --overlay-font-family: "Segoe UI", sans-serif;
      --overlay-text-color: #f4f4f5;
      --overlay-muted-opacity: 0.8;
      --overlay-card-bg: rgba(10, 10, 10, 0.75);
      --overlay-card-radius: 14px;
      --overlay-card-shadow: 0 8px 24px rgba(0, 0, 0, 0.45);
      --overlay-card-min-width: 320px;
      --overlay-card-gap: 16px;
      --overlay-card-padding-y: 16px;
      --overlay-card-padding-x: 20px;
      --overlay-cover-size: 96px;
      --overlay-cover-radius: 12px;
      --overlay-title-size: 18px;
      --overlay-artist-size: 14px;
      --overlay-time-size: 12px;
      --overlay-progress-track-bg: rgba(255, 255, 255, 0.2);
      --overlay-progress-height: 6px;
      --overlay-accent-start: #60a5fa;
      --overlay-accent-end: #34d399;
{theme_vars}
    }}
    body {{
      margin: 0;
      font-family: var(--overlay-font-family);
      background: transparent;
      color: var(--overlay-text-color);
    }}
    .card {{
      display: flex;
      align-items: center;
      gap: var(--overlay-card-gap);
      padding: var(--overlay-card-padding-y) var(--overlay-card-padding-x);
      background: var(--overlay-card-bg);
      border-radius: var(--overlay-card-radius);
      width: fit-content;
      min-width: var(--overlay-card-min-width);
      box-shadow: var(--overlay-card-shadow);
    }}
    .cover {{
      width: var(--overlay-cover-size);
      height: var(--overlay-cover-size);
      border-radius: var(--overlay-cover-radius);
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
      font-size: var(--overlay-title-size);
      font-weight: 600;
    }}
    .artist {{
      font-size: var(--overlay-artist-size);
      opacity: var(--overlay-muted-opacity);
      margin-top: 8px;
    }}
    .progress-track {{
      position: relative;
      height: var(--overlay-progress-height);
      border-radius: 999px;
      background: var(--overlay-progress-track-bg);
      margin-top: 12px;
      overflow: hidden;
    }}
    .progress-fill {{
      position: absolute;
      height: 100%;
      left: 0;
      top: 0;
      background: linear-gradient(90deg, var(--overlay-accent-start), var(--overlay-accent-end));
      width: 0%;
      transition: width 0.4s ease;
    }}
    .time {{
      font-size: var(--overlay-time-size);
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
    let nothingPlayingCoverUrl = {placeholder_cover!r};
    const titleEl = document.getElementById("title");
    const artistEl = document.getElementById("artist");
    const coverEl = document.getElementById("cover");{progress_js_vars}
    let currentPayload = null;{progress_js_functions}

    function applyNothingPlayingCover() {{
      if (nothingPlayingCoverUrl) {{
        coverEl.src = nothingPlayingCoverUrl;
        coverEl.classList.remove("default");
      }} else {{
        coverEl.removeAttribute("src");
        coverEl.classList.add("default");
      }}
    }}

    function applyPayload(payload) {{
      currentPayload = payload;
      if (!payload.isPlaying) {{
        titleEl.textContent = "Nothing playing";
        artistEl.textContent = "";
        applyNothingPlayingCover();{progress_reset}
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

    let refreshInFlight = false;
    let refreshStartedAtMs = 0;
    let lastAppliedServerTime = 0;

    async function refreshNowPlaying() {{
      const nowMs = Date.now();
      // If a previous request got stuck (rare, but can happen in embedded browsers),
      // don't let it block polling forever.
      const fetchTimeoutMs = Math.max(refreshMs * 3, 15000);
      if (refreshInFlight) {{
        if (refreshStartedAtMs && (nowMs - refreshStartedAtMs) > (fetchTimeoutMs + 2000)) {{
          refreshInFlight = false;
        }} else {{
          return;
        }}
      }}

      refreshInFlight = true;
      refreshStartedAtMs = nowMs;
      try {{
        // Add a cache-busting query param because some embedded browsers/proxies
        // may still serve cached responses even with Cache-Control: no-store.
        const url = "/api/now-playing?_=" + Date.now();
        let response;
        if (typeof AbortController !== "undefined") {{
          const controller = new AbortController();
          const timeoutId = setTimeout(() => controller.abort(), fetchTimeoutMs);
          try {{
            response = await fetch(url, {{ cache: "no-store", signal: controller.signal }});
          }} finally {{
            clearTimeout(timeoutId);
          }}
        }} else {{
          response = await fetch(url, {{ cache: "no-store" }});
        }}
        if (!response.ok) {{
          throw new Error("HTTP " + response.status);
        }}
        const payload = await response.json();
        // Debug: prove what the client is receiving.
        try {{
          const title = payload && payload.title ? String(payload.title) : "";
          const artist = payload && payload.artist ? String(payload.artist) : "";
          const state = payload && payload.isPlaying ? (payload.isPaused ? "PAUSED" : "PLAYING") : "NOT_PLAYING";
          console.log("[now-playing]", state, title, artist, "serverTime=" + (payload && payload.serverTime ? payload.serverTime : ""));
        }} catch (_) {{
          // Ignore logging errors.
        }}
        // Avoid applying older responses out of order (can happen after long throttles).
        const st = payload && payload.serverTime ? Number(payload.serverTime) : 0;
        if (st >= lastAppliedServerTime) {{
          lastAppliedServerTime = st;
          applyPayload(payload);
        }}
      }} catch (error) {{
        try {{
          console.warn("[now-playing] refresh failed", error);
        }} catch (_) {{
          // Ignore logging errors.
        }}
        titleEl.textContent = "Unable to reach Navidrome";
        artistEl.textContent = "";
        applyNothingPlayingCover();{progress_reset}
      }} finally {{
        refreshInFlight = false;
        refreshStartedAtMs = 0;
      }}
    }}

    refreshNowPlaying();
    setInterval(refreshNowPlaying, refreshMs);
    // Force a refresh when the source becomes visible/active again.
    document.addEventListener("visibilitychange", () => {{
      if (!document.hidden) {{
        refreshNowPlaying();
      }}
    }});
    window.addEventListener("focus", () => refreshNowPlaying());
    window.addEventListener("pageshow", () => refreshNowPlaying());{progress_interval}
  </script>
</body>
</html>
"""
    return html.encode("utf-8")
