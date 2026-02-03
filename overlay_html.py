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

    async function refreshNowPlaying() {{
      try {{
        const response = await fetch("/api/now-playing", {{ cache: "no-store" }});
        const payload = await response.json();
        applyPayload(payload);
      }} catch (error) {{
        titleEl.textContent = "Unable to reach Navidrome";
        artistEl.textContent = "";
        applyNothingPlayingCover();{progress_reset}
      }}
    }}

    refreshNowPlaying();
    setInterval(refreshNowPlaying, refreshMs);{progress_interval}
  </script>
</body>
</html>
"""
    return html.encode("utf-8")
