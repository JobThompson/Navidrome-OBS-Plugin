# Navidrome-OBS-Plugin

A lightweight Python overlay that exposes the currently playing song from Navidrome so you can
add it to OBS as a Browser source.

## Quick start

1. Copy the configuration below into a `.env` file next to `navidrome_obs_overlay.py`:

   ```ini
   NAVIDROME_URL=http://localhost:4533
   NAVIDROME_USER=your_user
   NAVIDROME_PASSWORD=your_password
   NAVIDROME_CLIENT_NAME=obs-overlay
   NAVIDROME_API_VERSION=1.16.1
   NAVIDROME_TIMEOUT=6
   OVERLAY_HOST=127.0.0.1
   OVERLAY_PORT=8080
   OVERLAY_REFRESH_SECONDS=1
   OVERLAY_SHOW_PROGRESS=false
   ```

2. Run the overlay server:

   ```bash
   python navidrome_obs_overlay.py
   ```

3. In OBS, add a **Browser** source that points to:

   ```
   http://127.0.0.1:8080
   ```

   Set the width/height to fit your scene (the overlay auto-sizes to its content).
   Default Viewport Size: 400x150

## What the overlay shows

- Album cover art
- Song title and artist
- Playback progress bar and timer (if enabled)
