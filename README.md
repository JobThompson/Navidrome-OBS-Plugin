# Navidrome-Plugin-Integration

A lightweight Python overlay that exposes the currently playing song from Navidrome so you can
add it to OBS as a Browser source.

## Quick start

### Windows (recommended)

1. Install **Python 3.10+** from https://www.python.org/downloads/
2. Double-click [Setup Overlay (GUI).bat](Setup%20Overlay%20(GUI).bat) and fill in your Navidrome URL + credentials.
3. Double-click [Start Overlay.bat](Start%20Overlay.bat)
4. In OBS, add a **Browser** source that points to:

   ```
   http://127.0.0.1:8080
   ```

### Manual setup (any OS)

1. Copy [\.env.example](.env.example) to `.env` and fill in your values (or run `python navidrome_obs_overlay.py --setup`):

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

   # When nothing is playing: dark | light | off
   OVERLAY_NOTHING_PLAYING_PLACEHOLDER=dark

   # Optional overlay theme
   OVERLAY_THEME_FONT_FAMILY="Segoe UI", sans-serif
   OVERLAY_THEME_TEXT_COLOR=#f4f4f5
   OVERLAY_THEME_CARD_BG=#000000
   OVERLAY_THEME_ACCENT_START=#60a5fa
   OVERLAY_THEME_ACCENT_END=#34d399
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

## Setup options

- Guided CLI setup: `python navidrome_obs_overlay.py --setup`
- Guided GUI setup (if available): `python navidrome_obs_overlay.py --gui`
- Open the overlay in your browser after starting: `python navidrome_obs_overlay.py --open`

## GUI setup

The GUI setup wizard is the easiest way to create/update your `.env` file.

**Run it:**

- Windows: double-click [Setup Overlay (GUI).bat](Setup%20Overlay%20(GUI).bat)
- Any OS: run:

   ```bash
   python navidrome_obs_overlay.py --gui
   ```

**What the buttons do:**

- **Detect** (next to “API version”): tries to auto-detect the Subsonic/Navidrome REST API version by calling `ping` on your server, then fills in the API version field.
- **Test connection**: validates your inputs and makes a lightweight request to Navidrome to confirm the URL/credentials work (does not start the overlay server).
- **Save**: writes your settings to `.env` and closes the GUI.
- **Save & Start**: writes your settings to `.env`, closes the GUI, and starts the overlay server.

**Tips:**

- Press `Esc` to close the setup window.
- The GUI requires Tkinter. If it isn’t available in your Python install, the app will fall back to the CLI setup.

## Developer notes

The implementation is split into small modules (config, API, server, HTML, setup wizard) to keep concerns separated.
End users should still run `python navidrome_obs_overlay.py ...` or the included `.bat` files.

## Troubleshooting

- **It says “Missing configuration”**: run the setup wizard (`--gui` or `--setup`) to create your `.env`.
- **Port already in use**: change `OVERLAY_PORT` in `.env` (8080 is common).
- **GUI won’t open**: run `python navidrome_obs_overlay.py --setup` (CLI setup), or install a Python build that includes Tkinter.

## What the overlay shows

- Album cover art
- Song title and artist
- Playback progress bar and timer

## Known Issues:

- When a song is paused, and the user skips the song, the API will not update until the next song finishes. This is an issue with the Navidrome API, and I've not found a way to fix it yet.
