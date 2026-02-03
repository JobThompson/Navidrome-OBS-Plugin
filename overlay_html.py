from __future__ import annotations


def render_index(refresh_seconds: int, show_progress: bool = True) -> bytes:
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
