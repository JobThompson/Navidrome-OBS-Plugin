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
    expand_width: bool = False,
    theme_css_vars: Optional[Dict[str, str]] = None,
    nothing_playing_cover_url: Optional[str] = None,
) -> bytes:
    theme_vars = _css_vars_block(theme_css_vars)

    card_width_rule = ""
    if expand_width:
        card_width_rule = "width: fit-content; min-width: var(--overlay-card-min-width); max-width: calc(100vw - 24px);"
    else:
        card_width_rule = "width: var(--overlay-card-min-width); min-width: var(--overlay-card-min-width); max-width: var(--overlay-card-min-width);"

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
      box-sizing: border-box;
      {card_width_rule}
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
      flex: 1 1 auto;
      min-width: 0;
    }}
    .title {{
      font-size: var(--overlay-title-size);
      font-weight: 600;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }}
    .artist {{
      font-size: var(--overlay-artist-size);
      opacity: var(--overlay-muted-opacity);
      margin-top: 8px;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }}
  </style>
</head>
<body>
  <div class="card">
    <img class="cover" id="cover" alt="Cover art" />
    <div class="info">
      <div class="title" id="title">Loading…</div>
      <div class="artist" id="artist"></div>
    </div>
  </div>

  <script>
    const refreshMs = {refresh_seconds * 1000};
    let nothingPlayingCoverUrl = {placeholder_cover!r};
    const titleEl = document.getElementById("title");
    const artistEl = document.getElementById("artist");
    const coverEl = document.getElementById("cover");
    let currentPayload = null;

    let lastCoverUrl = null;

    function applyCoverUrl(url) {{
      const next = url || "";
      if (lastCoverUrl === next) {{
        return;
      }}
      lastCoverUrl = next;
      if (next) {{
        coverEl.src = next;
        coverEl.classList.remove("default");
      }} else {{
        coverEl.removeAttribute("src");
        coverEl.classList.add("default");
      }}
    }}

    function applyNothingPlayingCover() {{
      applyCoverUrl(nothingPlayingCoverUrl);
    }}

    function applyPayload(payload) {{
      currentPayload = payload;
      if (!payload.isPlaying) {{
        titleEl.textContent = "Nothing playing";
        artistEl.textContent = "";
        applyNothingPlayingCover();
        return;
      }}

      titleEl.textContent = payload.title;
      artistEl.textContent = payload.artist || "";
      applyCoverUrl(payload.coverUrl || "");
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
        applyNothingPlayingCover();
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
    window.addEventListener("pageshow", () => refreshNowPlaying());
  </script>
</body>
</html>
"""
    return html.encode("utf-8")
