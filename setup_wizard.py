from __future__ import annotations

import getpass
import importlib.util
import sys
from pathlib import Path
from typing import Optional

from navidrome_api import detect_subsonic_api_version, fetch_now_playing
from overlay_config import load_config, load_env_file, write_env_file


def tkinter_available() -> bool:
    return importlib.util.find_spec("tkinter") is not None


def is_interactive() -> bool:
    try:
        return sys.stdin.isatty()
    except (AttributeError, OSError, ValueError):  # pragma: no cover
        return False


def parse_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def prompt(text: str, default: Optional[str] = None) -> str:
    suffix = f" [{default}]" if default not in (None, "") else ""
    while True:
        entered = input(f"{text}{suffix}: ").strip()
        if entered:
            return entered
        if default is not None:
            return default


def prompt_int(text: str, default: int, minimum: int = 1, maximum: int = 65535) -> int:
    while True:
        raw = prompt(text, str(default))
        try:
            value = int(raw)
        except ValueError:
            print("Please enter a number.")
            continue
        if value < minimum or value > maximum:
            print(f"Please enter a value between {minimum} and {maximum}.")
            continue
        return value


def prompt_bool(text: str, default: bool) -> bool:
    default_str = "yes" if default else "no"
    while True:
        raw = prompt(f"{text} (yes/no)", default_str).strip().lower()
        if raw in {"yes", "y", "1", "true", "on"}:
            return True
        if raw in {"no", "n", "0", "false", "off"}:
            return False
        print("Please enter yes or no.")


def run_cli_setup(env_path: Path) -> None:
    existing = load_env_file(env_path)
    print("\nNavidrome OBS Overlay - guided setup\n")

    navidrome_url_default = existing.get("NAVIDROME_URL", "http://localhost:4533")
    navidrome_url = prompt("Navidrome URL", navidrome_url_default).rstrip("/")
    while not (navidrome_url.startswith("http://") or navidrome_url.startswith("https://")):
        print("Please enter a URL that starts with http:// or https://")
        navidrome_url = prompt("Navidrome URL", navidrome_url_default).rstrip("/")

    navidrome_user = prompt("Navidrome username", existing.get("NAVIDROME_USER", ""))

    existing_password = existing.get("NAVIDROME_PASSWORD", "")
    if existing_password:
        change_password = prompt_bool("Update saved Navidrome password?", False)
        if change_password:
            navidrome_password = getpass.getpass("Navidrome password: ").strip()
        else:
            navidrome_password = existing_password
    else:
        navidrome_password = getpass.getpass("Navidrome password: ").strip()

    navidrome_client = prompt(
        "Client name (shows up in Navidrome)", existing.get("NAVIDROME_CLIENT_NAME", "obs-overlay")
    )
    navidrome_version = prompt(
        "Subsonic API version", existing.get("NAVIDROME_API_VERSION", "1.16.1")
    )
    timeout = prompt_int(
        "Request timeout (seconds)", int(float(existing.get("NAVIDROME_TIMEOUT", "6") or "6")), 1, 120
    )
    host = prompt("Overlay host", existing.get("OVERLAY_HOST", "127.0.0.1"))
    port = prompt_int("Overlay port", int(existing.get("OVERLAY_PORT", "8080") or "8080"), 1, 65535)
    refresh = prompt_int(
        "Refresh interval (seconds)", int(existing.get("OVERLAY_REFRESH_SECONDS", "1") or "1"), 1, 60
    )
    show_progress = prompt_bool(
        "Show progress bar + time", parse_bool(existing.get("OVERLAY_SHOW_PROGRESS", "false"))
    )

    placeholder_default = (existing.get("OVERLAY_NOTHING_PLAYING_PLACEHOLDER", "dark") or "dark").strip().lower()
    if placeholder_default not in {"dark", "light", "off"}:
        placeholder_default = "dark"
    placeholder_choice = prompt(
        "Nothing playing image (dark/light/off)", placeholder_default
    ).strip().lower()
    if placeholder_choice in {"none", "false", "0"}:
        placeholder_choice = "off"
    if placeholder_choice not in {"dark", "light", "off"}:
        print("Unknown choice; defaulting to 'dark'.")
        placeholder_choice = "dark"

    values = {
        "NAVIDROME_URL": navidrome_url,
        "NAVIDROME_USER": navidrome_user,
        "NAVIDROME_PASSWORD": navidrome_password,
        "NAVIDROME_CLIENT_NAME": navidrome_client,
        "NAVIDROME_API_VERSION": navidrome_version,
        "NAVIDROME_TIMEOUT": str(timeout),
        "OVERLAY_HOST": host,
        "OVERLAY_PORT": str(port),
        "OVERLAY_REFRESH_SECONDS": str(refresh),
        "OVERLAY_SHOW_PROGRESS": "true" if show_progress else "false",
        "OVERLAY_NOTHING_PLAYING_PLACEHOLDER": placeholder_choice,
    }

    write_env_file(env_path, values)
    print(f"\nSaved configuration to {env_path}\n")

    try:
        config = load_config(env_path)
        _ = fetch_now_playing(config)
        print("Navidrome connection check: OK (request succeeded)")
    except Exception as exc:  # pylint: disable=broad-except
        print(f"Navidrome connection check: FAILED ({type(exc).__name__}: {exc})")
        print("You can still start the overlay; verify URL/credentials if needed.")


def run_gui_setup(env_path: Path) -> Optional[bool]:
    """Returns True for Save&Start, False for Save, None for cancel."""

    try:
        import tkinter as tk
        from tkinter import colorchooser, messagebox
        from tkinter import font as tkfont
    except ImportError:
        return None

    existing = load_env_file(env_path)

    # Material-ish theme (best-effort within Tkinter)
    APP_BG = "#f5f5f5"  # gray 100
    SURFACE = "#ffffff"
    TEXT = "#202124"
    TEXT_MUTED = "#5f6368"
    PRIMARY = "#1976d2"  # blue 700
    PRIMARY_HOVER = "#1565c0"
    BORDER = "#e0e0e0"
    SUCCESS = "#2e7d32"
    ERROR = "#d32f2f"
    FONT = "Segoe UI"

    root = tk.Tk()
    root.title("Navidrome OBS Overlay Setup")
    root.geometry("860x860")
    root.minsize(720, 600)
    root.resizable(True, True)
    root.configure(bg=APP_BG)
    root.columnconfigure(0, weight=1)
    root.rowconfigure(1, weight=1)

    url_var = tk.StringVar(value=existing.get("NAVIDROME_URL", "http://localhost:4533"))
    user_var = tk.StringVar(value=existing.get("NAVIDROME_USER", ""))
    pass_var = tk.StringVar(value=existing.get("NAVIDROME_PASSWORD", ""))
    client_var = tk.StringVar(value=existing.get("NAVIDROME_CLIENT_NAME", "obs-overlay"))
    version_var = tk.StringVar(value=existing.get("NAVIDROME_API_VERSION", "1.16.1"))
    timeout_var = tk.StringVar(value=existing.get("NAVIDROME_TIMEOUT", "6"))
    host_var = tk.StringVar(value=existing.get("OVERLAY_HOST", "127.0.0.1"))
    port_var = tk.StringVar(value=existing.get("OVERLAY_PORT", "8080"))
    refresh_var = tk.StringVar(value=existing.get("OVERLAY_REFRESH_SECONDS", "1"))
    progress_var = tk.BooleanVar(value=parse_bool(existing.get("OVERLAY_SHOW_PROGRESS", "false")))

    placeholder_value_var = tk.StringVar(
        value=(existing.get("OVERLAY_NOTHING_PLAYING_PLACEHOLDER", "dark") or "dark").strip().lower()
    )
    PLACEHOLDER_OPTIONS: dict[str, str] = {
        "Dark image": "dark",
        "Light image": "light",
        "Icon only": "off",
    }
    placeholder_label_var = tk.StringVar(value="Dark image")
    for label, value in PLACEHOLDER_OPTIONS.items():
        if placeholder_value_var.get() == value:
            placeholder_label_var.set(label)
            break

    theme_font_var = tk.StringVar(
        value=existing.get("OVERLAY_THEME_FONT_FAMILY", '"Segoe UI", sans-serif')
    )
    theme_font_preset_var = tk.StringVar(value="Custom…")
    theme_text_color_var = tk.StringVar(
        value=existing.get("OVERLAY_THEME_TEXT_COLOR", "#f4f4f5")
    )
    theme_card_bg_var = tk.StringVar(
        value=existing.get("OVERLAY_THEME_CARD_BG", "rgba(10, 10, 10, 0.75)")
    )
    theme_card_radius_var = tk.StringVar(
        value=existing.get("OVERLAY_THEME_CARD_RADIUS_PX", "14")
    )
    theme_accent_start_var = tk.StringVar(
        value=existing.get("OVERLAY_THEME_ACCENT_START", "#60a5fa")
    )
    theme_accent_end_var = tk.StringVar(
        value=existing.get("OVERLAY_THEME_ACCENT_END", "#34d399")
    )
    theme_cover_size_var = tk.StringVar(
        value=existing.get("OVERLAY_THEME_COVER_SIZE_PX", "96")
    )
    theme_min_width_var = tk.StringVar(
        value=existing.get("OVERLAY_THEME_CARD_MIN_WIDTH_PX", "320")
    )
    theme_title_size_var = tk.StringVar(
        value=existing.get("OVERLAY_THEME_TITLE_SIZE_PX", "18")
    )
    theme_artist_size_var = tk.StringVar(
        value=existing.get("OVERLAY_THEME_ARTIST_SIZE_PX", "14")
    )

    FONT_PRESETS: dict[str, str] = {
        "Default (Segoe UI)": '"Segoe UI", sans-serif',
        "Arial": '"Arial", sans-serif',
        "Verdana": '"Verdana", sans-serif',
        "Tahoma": '"Tahoma", sans-serif',
        "Trebuchet MS": '"Trebuchet MS", sans-serif',
        "Helvetica": '"Helvetica", Arial, sans-serif',
        "Georgia": '"Georgia", serif',
        "Times New Roman": '"Times New Roman", serif',
        "Consolas (mono)": '"Consolas", monospace',
        "Cascadia Mono (mono)": '"Cascadia Mono", monospace',
    }

    # Best-effort: map existing CSS string back to a preset label.
    current_font_value = theme_font_var.get().strip()
    for label, css_value in FONT_PRESETS.items():
        if current_font_value == css_value:
            theme_font_preset_var.set(label)
            break

    start_choice: dict[str, Optional[bool]] = {"start": None}

    def make_card(parent: tk.Widget, title: str) -> tuple[tk.Frame, tk.Frame]:
        card = tk.Frame(parent, bg=SURFACE, highlightthickness=1, highlightbackground=BORDER)
        card_title = tk.Label(
            card,
            text=title,
            bg=SURFACE,
            fg=TEXT,
            font=(FONT, 10, "bold"),
            anchor="w",
        )
        card_title.grid(row=0, column=0, sticky="ew", padx=14, pady=(12, 8))
        body = tk.Frame(card, bg=SURFACE)
        body.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 14))
        card.columnconfigure(0, weight=1)
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=1)
        return card, body

    def style_text_button(button: tk.Button) -> None:
        button.configure(
            bg=APP_BG,
            fg=PRIMARY,
            activebackground=APP_BG,
            activeforeground=PRIMARY_HOVER,
            relief="flat",
            bd=0,
            highlightthickness=0,
            font=(FONT, 9, "bold"),
            cursor="hand2",
            padx=2,
            pady=2,
        )

    def style_header_text_button(button: tk.Button) -> None:
        button.configure(
            bg=PRIMARY,
            fg="#dbeafe",
            activebackground=PRIMARY,
            activeforeground="#ffffff",
            relief="flat",
            bd=0,
            highlightthickness=0,
            font=(FONT, 9, "bold"),
            cursor="hand2",
            padx=6,
            pady=2,
        )

    def style_header_primary_button(button: tk.Button) -> None:
        # High-contrast CTA on the blue header.
        button.configure(
            bg="#ffffff",
            fg=PRIMARY,
            activebackground="#e3f2fd",
            activeforeground=PRIMARY,
            relief="flat",
            bd=0,
            highlightthickness=0,
            font=(FONT, 9, "bold"),
            cursor="hand2",
            padx=14,
            pady=9,
        )

    def style_header_outlined_button(button: tk.Button) -> None:
        button.configure(
            bg=PRIMARY,
            fg="#ffffff",
            activebackground=PRIMARY_HOVER,
            activeforeground="#ffffff",
            relief="flat",
            bd=0,
            highlightthickness=1,
            highlightbackground="#bbdefb",
            highlightcolor="#bbdefb",
            font=(FONT, 9, "bold"),
            cursor="hand2",
            padx=14,
            pady=9,
        )

    def _rounded_rect(
        canvas: tk.Canvas,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        radius: int,
        **kwargs: object,
    ) -> int:
        r = max(0, min(radius, (x2 - x1) // 2, (y2 - y1) // 2))
        points = [
            x1 + r,
            y1,
            x2 - r,
            y1,
            x2,
            y1,
            x2,
            y1 + r,
            x2,
            y2 - r,
            x2,
            y2,
            x2 - r,
            y2,
            x1 + r,
            y2,
            x1,
            y2,
            x1,
            y2 - r,
            x1,
            y1 + r,
            x1,
            y1,
        ]
        return canvas.create_polygon(points, smooth=True, splinesteps=24, **kwargs)

    def make_rounded_entry(
        parent: tk.Widget, variable: tk.Variable, *, show: Optional[str] = None
    ) -> tuple[tk.Frame, tk.Entry]:
        container = tk.Frame(parent, bg=SURFACE)
        canvas = tk.Canvas(container, bg=SURFACE, highlightthickness=0, bd=0, height=36)
        canvas.pack(fill="x", expand=True)

        entry = tk.Entry(
            canvas,
            textvariable=variable,
            show=show,
            relief="flat",
            bd=0,
            bg=SURFACE,
            fg=TEXT,
            insertbackground=TEXT,
            font=(FONT, 10),
        )

        entry_window = canvas.create_window(14, 18, window=entry, anchor="w")
        state: dict[str, str] = {"border": BORDER}

        def redraw() -> None:
            canvas.delete("shape")
            width = canvas.winfo_width()
            height = canvas.winfo_height()
            if width <= 2 or height <= 2:
                return
            _rounded_rect(
                canvas,
                1,
                1,
                width - 1,
                height - 1,
                10,
                fill=SURFACE,
                outline=state["border"],
                width=1,
                tags=("shape",),
            )
            canvas.tag_lower("shape")
            canvas.coords(entry_window, 14, height // 2)
            canvas.itemconfigure(entry_window, width=max(10, width - 28), height=max(10, height - 12))

        def on_focus_in(_event: object) -> None:
            state["border"] = PRIMARY
            redraw()

        def on_focus_out(_event: object) -> None:
            state["border"] = BORDER
            redraw()

        canvas.bind("<Configure>", lambda _e: redraw())
        entry.bind("<FocusIn>", on_focus_in)
        entry.bind("<FocusOut>", on_focus_out)
        entry.bind("<Return>", lambda _e: None)
        container.after_idle(redraw)

        return container, entry

    def add_field(
        parent: tk.Frame,
        row: int,
        col: int,
        label: str,
        variable: tk.Variable,
        *,
        show: Optional[str] = None,
        colspan: int = 1,
    ) -> tk.Entry:
        tk.Label(parent, text=label, bg=SURFACE, fg=TEXT_MUTED, font=(FONT, 9), anchor="w").grid(
            row=row * 2,
            column=col,
            columnspan=colspan,
            sticky="w",
            pady=(0, 3),
            padx=(0, 12) if col == 0 else 0,
        )
        entry_container, entry = make_rounded_entry(parent, variable, show=show)
        entry_container.grid(
            row=row * 2 + 1,
            column=col,
            columnspan=colspan,
            sticky="ew",
            pady=(0, 12),
            padx=(0, 12) if col == 0 else 0,
        )
        return entry

    def add_field_with_button(
        parent: tk.Frame,
        row: int,
        col: int,
        label: str,
        variable: tk.Variable,
        *,
        button_text: str,
        command: object,
        show: Optional[str] = None,
    ) -> tk.Entry:
        tk.Label(parent, text=label, bg=SURFACE, fg=TEXT_MUTED, font=(FONT, 9), anchor="w").grid(
            row=row * 2,
            column=col,
            sticky="w",
            pady=(0, 3),
        )

        row_frame = tk.Frame(parent, bg=SURFACE)
        row_frame.grid(row=row * 2 + 1, column=col, sticky="ew", pady=(0, 12))
        row_frame.columnconfigure(0, weight=1)

        entry_container, entry = make_rounded_entry(row_frame, variable, show=show)
        entry_container.grid(row=0, column=0, sticky="ew")

        button = tk.Button(row_frame, text=button_text, command=command)
        style_text_button(button)
        button.grid(row=0, column=1, sticky="e", padx=(10, 0))

        return entry

    def add_dropdown(
        parent: tk.Frame,
        row: int,
        col: int,
        label: str,
        variable: tk.Variable,
        options: list[str],
        *,
        colspan: int = 1,
    ) -> tk.OptionMenu:
        tk.Label(parent, text=label, bg=SURFACE, fg=TEXT_MUTED, font=(FONT, 9), anchor="w").grid(
            row=row * 2,
            column=col,
            columnspan=colspan,
            sticky="w",
            pady=(0, 3),
            padx=(0, 12) if col == 0 else 0,
        )

        container = tk.Frame(parent, bg=SURFACE)
        container.grid(
            row=row * 2 + 1,
            column=col,
            columnspan=colspan,
            sticky="ew",
            pady=(0, 12),
            padx=(0, 12) if col == 0 else 0,
        )
        container.columnconfigure(0, weight=1)

        menu = tk.OptionMenu(container, variable, *options)
        menu.configure(
            bg=SURFACE,
            fg=TEXT,
            activebackground="#f0f0f0",
            activeforeground=TEXT,
            relief="flat",
            bd=0,
            highlightthickness=1,
            highlightbackground=BORDER,
            highlightcolor=BORDER,
            font=(FONT, 10),
            cursor="hand2",
            padx=8,
            pady=6,
        )
        menu["menu"].configure(bg=SURFACE, fg=TEXT, activebackground="#eeeeee")
        menu.grid(row=0, column=0, sticky="ew")
        return menu

    def pick_color_into(var: tk.StringVar, *, prefer_rgba_alpha_from: Optional[tk.StringVar] = None) -> None:
        initial = var.get().strip() or "#ffffff"
        chosen = colorchooser.askcolor(color=initial)
        if not chosen or not chosen[1]:
            return
        hex_color = chosen[1]

        # If the existing value is rgba(..., a) keep its alpha when replacing.
        if prefer_rgba_alpha_from is not None:
            raw = prefer_rgba_alpha_from.get().strip()
            if raw.lower().startswith("rgba(") and raw.endswith(")"):
                try:
                    inner = raw[5:-1]
                    parts = [p.strip() for p in inner.split(",")]
                    if len(parts) == 4:
                        alpha = float(parts[3])
                        r = int(hex_color[1:3], 16)
                        g = int(hex_color[3:5], 16)
                        b = int(hex_color[5:7], 16)
                        var.set(f"rgba({r}, {g}, {b}, {alpha:g})")
                        return
                except Exception:  # pylint: disable=broad-except
                    pass

        var.set(hex_color)

    def enable_color_picker_on_click(
        entry: tk.Entry,
        var: tk.StringVar,
        *,
        prefer_rgba_alpha_from: Optional[tk.StringVar] = None,
    ) -> None:
        state: dict[str, bool] = {"open": False}

        def on_click(_event: object) -> None:
            # Don't interfere with normal entry behavior; open picker async.
            if state["open"]:
                return

            def _open() -> None:
                state["open"] = True
                try:
                    pick_color_into(var, prefer_rgba_alpha_from=prefer_rgba_alpha_from)
                finally:
                    state["open"] = False

            entry.after(1, _open)

        entry.bind("<Button-1>", on_click, add=True)

    # Layout root
    header = tk.Frame(root, bg=PRIMARY)
    header.grid(row=0, column=0, sticky="ew")
    header.columnconfigure(0, weight=1)
    header.columnconfigure(1, weight=0)
    tk.Label(
        header,
        text="Navidrome OBS Overlay",
        bg=PRIMARY,
        fg="#ffffff",
        font=(FONT, 16, "bold"),
        anchor="w",
    ).grid(row=0, column=0, sticky="ew", padx=18, pady=(14, 2))
    tk.Label(
        header,
        text="Setup",
        bg=PRIMARY,
        fg="#dbeafe",
        font=(FONT, 10),
        anchor="w",
    ).grid(row=1, column=0, sticky="ew", padx=18, pady=(0, 12))

    header_actions = tk.Frame(header, bg=PRIMARY)
    header_actions.grid(row=0, column=1, rowspan=2, sticky="e", padx=(0, 18), pady=(12, 12))

    header_test_button = tk.Button(header_actions, text="Test connection", command=lambda: None)
    style_header_text_button(header_test_button)
    header_test_button.grid(row=0, column=0, sticky="e", padx=(0, 10))

    header_save_button = tk.Button(header_actions, text="Save", command=lambda: None)
    style_header_outlined_button(header_save_button)
    header_save_button.grid(row=0, column=1, sticky="e", padx=(0, 10))

    header_start_button = tk.Button(header_actions, text="Save & Start", command=lambda: None)
    style_header_primary_button(header_start_button)
    header_start_button.grid(row=0, column=2, sticky="e")

    # Scrollable content (so the window can resize and scroll on overflow)
    scroll_area = tk.Frame(root, bg=APP_BG)
    scroll_area.grid(row=1, column=0, sticky="nsew")
    scroll_area.columnconfigure(0, weight=1)
    scroll_area.rowconfigure(0, weight=1)

    scroll_canvas = tk.Canvas(scroll_area, bg=APP_BG, highlightthickness=0, bd=0)
    scroll_canvas.grid(row=0, column=0, sticky="nsew")

    v_scrollbar = tk.Scrollbar(scroll_area, orient="vertical", command=scroll_canvas.yview)
    v_scrollbar.grid(row=0, column=1, sticky="ns")
    scroll_canvas.configure(yscrollcommand=v_scrollbar.set)

    content = tk.Frame(scroll_canvas, bg=APP_BG)
    content.columnconfigure(0, weight=1)
    content_window = scroll_canvas.create_window((0, 0), window=content, anchor="nw")

    def _on_content_configure(_event: object) -> None:
        scroll_canvas.configure(scrollregion=scroll_canvas.bbox("all"))

    def _on_canvas_configure(_event: object) -> None:
        # Make the inner frame match the available canvas width.
        width = scroll_canvas.winfo_width()
        scroll_canvas.itemconfigure(content_window, width=width)
        # Keep the status label wrapping sensible as the window width changes.
        try:
            status_label.configure(wraplength=max(320, width - 32))
        except Exception:  # pylint: disable=broad-except
            pass

    content.bind("<Configure>", _on_content_configure)
    scroll_canvas.bind("<Configure>", _on_canvas_configure)

    def _on_mousewheel(event: object) -> None:
        # Windows: event.delta is multiples of 120.
        delta = getattr(event, "delta", 0)
        if delta:
            scroll_canvas.yview_scroll(int(-1 * (delta / 120)), "units")

    scroll_canvas.bind_all("<MouseWheel>", _on_mousewheel)

    status_text = tk.StringVar(value="")
    status_label = tk.Label(
        content,
        textvariable=status_text,
        bg=APP_BG,
        fg=TEXT_MUTED,
        anchor="w",
        justify="left",
        font=(FONT, 9),
        wraplength=760,
    )
    status_label.grid(row=0, column=0, sticky="ew", pady=(0, 12))

    nav_card, nav_body = make_card(content, "Navidrome")
    nav_card.grid(row=1, column=0, sticky="ew")

    overlay_card, overlay_body = make_card(content, "Overlay")
    overlay_card.grid(row=2, column=0, sticky="ew", pady=(12, 0))

    theme_card, theme_body = make_card(content, "Theme")
    theme_card.grid(row=3, column=0, sticky="ew", pady=(12, 0))

    preview_card, preview_body = make_card(content, "Preview")
    preview_card.grid(row=4, column=0, sticky="ew", pady=(12, 0))

    url_entry = add_field(nav_body, 0, 0, "Navidrome URL", url_var, colspan=2)
    add_field(nav_body, 1, 0, "Username", user_var)
    add_field(nav_body, 1, 1, "Password", pass_var, show="*")
    add_field(nav_body, 2, 0, "Client name", client_var)

    def set_status(message: str, *, kind: str = "info") -> None:
        status_text.set(message)
        if kind == "ok":
            status_label.configure(fg=SUCCESS)
        elif kind == "error":
            status_label.configure(fg=ERROR)
        elif kind == "working":
            status_label.configure(fg=PRIMARY)
        else:
            status_label.configure(fg=TEXT_MUTED)

    def clear_status(*_args: object) -> None:
        if status_text.get():
            set_status("")

    for var in (
        url_var,
        user_var,
        pass_var,
        client_var,
        version_var,
        timeout_var,
        host_var,
        port_var,
        refresh_var,
        placeholder_value_var,
        placeholder_label_var,
        theme_font_var,
        theme_font_preset_var,
        theme_text_color_var,
        theme_card_bg_var,
        theme_card_radius_var,
        theme_accent_start_var,
        theme_accent_end_var,
        theme_cover_size_var,
        theme_min_width_var,
        theme_title_size_var,
        theme_artist_size_var,
    ):
        var.trace_add("write", clear_status)

    progress_var.trace_add("write", clear_status)

    def _parse_int(raw: str, default: int) -> int:
        try:
            return int((raw or "").strip())
        except ValueError:
            return default

    def _css_color_to_tk(raw: str, default: str) -> str:
        """Convert a CSS-ish color to something Tk can use (best-effort)."""

        value = (raw or "").strip()
        if not value:
            return default
        if value.startswith("#"):
            return value
        if value.lower().startswith("rgb(") and value.endswith(")"):
            try:
                inner = value[4:-1]
                parts = [p.strip() for p in inner.split(",")]
                if len(parts) >= 3:
                    r, g, b = (int(float(parts[0])), int(float(parts[1])), int(float(parts[2])))
                    return f"#{r:02x}{g:02x}{b:02x}"
            except Exception:  # pylint: disable=broad-except
                return default
        if value.lower().startswith("rgba(") and value.endswith(")"):
            try:
                inner = value[5:-1]
                parts = [p.strip() for p in inner.split(",")]
                if len(parts) >= 3:
                    r, g, b = (int(float(parts[0])), int(float(parts[1])), int(float(parts[2])))
                    return f"#{r:02x}{g:02x}{b:02x}"
            except Exception:  # pylint: disable=broad-except
                return default

        # Named colors might work; otherwise, fall back.
        return value

    def _first_font_family(css_font_family: str) -> str:
        raw = (css_font_family or "").strip()
        if not raw:
            return FONT
        first = raw.split(",", 1)[0].strip().strip('"').strip("'")
        return first or FONT

    # --- Preview (in-page, best-effort to match overlay layout) ---
    preview_surface = tk.Frame(preview_body, bg=APP_BG)
    preview_surface.grid(row=0, column=0, sticky="ew")
    preview_surface.columnconfigure(0, weight=1)

    tk.Label(
        preview_surface,
        text="Preview",
        bg=APP_BG,
        fg=TEXT,
        font=(FONT, 10, "bold"),
        anchor="w",
    ).grid(row=0, column=0, sticky="w", pady=(0, 6))

    preview_canvas = tk.Canvas(preview_surface, bg=APP_BG, highlightthickness=0, bd=0, height=240)
    preview_canvas.grid(row=1, column=0, sticky="ew")

    # Default to "Nothing playing" so the placeholder (dark/light/off) choice is visible immediately.
    preview_state_var = tk.StringVar(value="Nothing playing")
    preview_controls = tk.Frame(preview_surface, bg=APP_BG)
    preview_controls.grid(row=2, column=0, sticky="ew", pady=(8, 0))
    tk.Label(preview_controls, text="State", bg=APP_BG, fg=TEXT_MUTED, anchor="w").grid(
        row=0, column=0, sticky="w", padx=(0, 8)
    )
    state_menu = tk.OptionMenu(preview_controls, preview_state_var, "Playing", "Nothing playing")
    state_menu.configure(bg=SURFACE, fg=TEXT, activebackground=SURFACE, activeforeground=TEXT)
    state_menu.grid(row=0, column=1, sticky="w")

    placeholder_preview_state: dict[str, object] = {
        "raw": {},
        "scaled": {},
        "last": None,
    }

    def _get_placeholder_image(variant: str, size_px: int) -> Optional[tk.PhotoImage]:
        if variant not in {"dark", "light"}:
            return None

        assets_dir = Path(__file__).with_name("assets")
        filename = "Nothing Playing Dark.png" if variant == "dark" else "Nothing Playing Light.png"
        path = assets_dir / filename
        if not path.exists():
            return None

        raw_cache: dict[str, tk.PhotoImage] = placeholder_preview_state["raw"]  # type: ignore[assignment]
        scaled_cache: dict[tuple[str, int], tk.PhotoImage] = placeholder_preview_state["scaled"]  # type: ignore[assignment]

        if variant not in raw_cache:
            try:
                raw_cache[variant] = tk.PhotoImage(file=str(path))
            except Exception:  # pylint: disable=broad-except
                return None

        raw_img = raw_cache[variant]
        key = (variant, int(size_px))
        if key in scaled_cache:
            return scaled_cache[key]

        # Best-effort scaling using integer zoom/subsample.
        w = max(1, raw_img.width())
        h = max(1, raw_img.height())
        target = max(16, int(size_px))

        subsample_factor = max(1, int(round(max(w, h) / target)))
        img = raw_img.subsample(subsample_factor, subsample_factor) if subsample_factor > 1 else raw_img

        w2 = max(1, img.width())
        h2 = max(1, img.height())
        zoom_factor = max(1, int(target / max(w2, h2)))
        if zoom_factor > 1:
            img = img.zoom(zoom_factor, zoom_factor)

        scaled_cache[key] = img
        return img

    def _hex_to_rgb(value: str) -> Optional[tuple[int, int, int]]:
        v = (value or "").strip()
        if not v.startswith("#"):
            return None
        h = v[1:]
        if len(h) == 3:
            try:
                r = int(h[0] * 2, 16)
                g = int(h[1] * 2, 16)
                b = int(h[2] * 2, 16)
                return (r, g, b)
            except ValueError:
                return None
        if len(h) == 6:
            try:
                r = int(h[0:2], 16)
                g = int(h[2:4], 16)
                b = int(h[4:6], 16)
                return (r, g, b)
            except ValueError:
                return None
        return None

    def _rgb_to_hex(rgb: tuple[int, int, int]) -> str:
        r, g, b = rgb
        return f"#{max(0, min(255, r)):02x}{max(0, min(255, g)):02x}{max(0, min(255, b)):02x}"

    def _blend(bg: tuple[int, int, int], fg: tuple[int, int, int], alpha: float) -> tuple[int, int, int]:
        a = max(0.0, min(1.0, float(alpha)))
        return (
            int(bg[0] + (fg[0] - bg[0]) * a),
            int(bg[1] + (fg[1] - bg[1]) * a),
            int(bg[2] + (fg[2] - bg[2]) * a),
        )

    def _create_round_rect(x1: int, y1: int, x2: int, y2: int, r: int, *, fill: str) -> int:
        rr = max(0, int(r))
        rr = min(rr, int((x2 - x1) / 2), int((y2 - y1) / 2))
        points = [
            x1 + rr,
            y1,
            x2 - rr,
            y1,
            x2,
            y1,
            x2,
            y1 + rr,
            x2,
            y2 - rr,
            x2,
            y2,
            x2 - rr,
            y2,
            x1 + rr,
            y2,
            x1,
            y2,
            x1,
            y2 - rr,
            x1,
            y1 + rr,
            x1,
            y1,
        ]
        return preview_canvas.create_polygon(points, smooth=True, splinesteps=36, fill=fill, outline="")

    _preview_after_id: Optional[str] = None

    def _schedule_preview_redraw(*_args: object) -> None:
        nonlocal _preview_after_id
        if _preview_after_id is not None:
            try:
                root.after_cancel(_preview_after_id)
            except Exception:  # pylint: disable=broad-except
                pass
        _preview_after_id = root.after(50, _redraw_preview)

    def _redraw_preview() -> None:
        nonlocal _preview_after_id
        _preview_after_id = None

        preview_canvas.delete("all")

        # Read theme values (defaults aligned with overlay_html.py)
        css_font = theme_font_var.get() or '"Segoe UI", sans-serif'
        font_family = _first_font_family(css_font)
        text_color_hex = _css_color_to_tk(theme_text_color_var.get(), "#f4f4f5")
        card_bg_raw = theme_card_bg_var.get() or "rgba(10, 10, 10, 0.75)"
        accent_start_raw = theme_accent_start_var.get() or "#60a5fa"
        accent_end_raw = theme_accent_end_var.get() or "#34d399"

        card_radius = _parse_int(theme_card_radius_var.get(), 14)
        card_gap = _parse_int(existing.get("OVERLAY_THEME_CARD_GAP_PX", "16"), 16)
        pad_x = _parse_int(existing.get("OVERLAY_THEME_CARD_PADDING_X_PX", "20"), 20)
        pad_y = _parse_int(existing.get("OVERLAY_THEME_CARD_PADDING_Y_PX", "16"), 16)
        cover_size = _parse_int(theme_cover_size_var.get(), 96)
        cover_radius = _parse_int(existing.get("OVERLAY_THEME_COVER_RADIUS_PX", "12"), 12)
        min_width = _parse_int(theme_min_width_var.get(), 320)
        title_size = _parse_int(theme_title_size_var.get(), 18)
        artist_size = _parse_int(theme_artist_size_var.get(), 14)
        time_size = _parse_int(existing.get("OVERLAY_THEME_TIME_SIZE_PX", "12"), 12)
        muted_opacity = float(existing.get("OVERLAY_THEME_MUTED_OPACITY", "0.8") or "0.8")
        progress_height = _parse_int(existing.get("OVERLAY_THEME_PROGRESS_HEIGHT_PX", "6"), 6)
        progress_track_bg_raw = existing.get("OVERLAY_THEME_PROGRESS_TRACK_BG", "rgba(255, 255, 255, 0.2)")

        # Tk can't do true alpha like CSS; approximate by dropping alpha and blending against a dark "preview background".
        preview_bg_rgb = _hex_to_rgb("#0b0b0b") or (11, 11, 11)

        def _rgba_to_rgb_approx(css: str, fallback: tuple[int, int, int]) -> tuple[int, int, int]:
            v = (css or "").strip().lower()
            if v.startswith("rgba(") and v.endswith(")"):
                try:
                    inner = v[5:-1]
                    parts = [p.strip() for p in inner.split(",")]
                    if len(parts) >= 4:
                        r = int(float(parts[0]))
                        g = int(float(parts[1]))
                        b = int(float(parts[2]))
                        a = float(parts[3])
                        return _blend(preview_bg_rgb, (r, g, b), a)
                except Exception:  # pylint: disable=broad-except
                    return fallback
            if v.startswith("rgb(") and v.endswith(")"):
                try:
                    inner = v[4:-1]
                    parts = [p.strip() for p in inner.split(",")]
                    if len(parts) >= 3:
                        r = int(float(parts[0]))
                        g = int(float(parts[1]))
                        b = int(float(parts[2]))
                        return (r, g, b)
                except Exception:  # pylint: disable=broad-except
                    return fallback

            rgb = _hex_to_rgb(_css_color_to_tk(css, _rgb_to_hex(fallback)))
            return rgb or fallback

        card_bg_rgb = _rgba_to_rgb_approx(card_bg_raw, (10, 10, 10))
        card_bg_hex = _rgb_to_hex(card_bg_rgb)

        text_rgb = _hex_to_rgb(_css_color_to_tk(text_color_hex, "#f4f4f5")) or (244, 244, 245)
        artist_rgb = _blend(card_bg_rgb, text_rgb, muted_opacity)

        accent_start_rgb = _rgba_to_rgb_approx(accent_start_raw, (96, 165, 250))
        accent_end_rgb = _rgba_to_rgb_approx(accent_end_raw, (52, 211, 153))
        track_rgb = _rgba_to_rgb_approx(progress_track_bg_raw, (255, 255, 255))
        track_hex = _rgb_to_hex(track_rgb)

        show_progress_preview = bool(progress_var.get())

        # Layout (mirrors overlay CSS)
        margin = 10
        info_min_w = 180
        card_w = max(min_width, pad_x * 2 + cover_size + card_gap + info_min_w)
        info_w = max(info_min_w, card_w - (pad_x * 2 + cover_size + card_gap))

        title_artist_gap = 8
        content_h = max(cover_size, title_size + title_artist_gap + artist_size)
        if show_progress_preview:
            content_h = max(
                content_h,
                title_size + title_artist_gap + artist_size + 12 + progress_height + 8 + time_size,
            )
        card_h = pad_y * 2 + content_h

        # Expand canvas height to fit card
        preview_canvas.configure(height=max(160, card_h + margin * 2))

        x1 = margin
        y1 = margin
        x2 = x1 + card_w
        y2 = y1 + card_h

        # Soft shadow approximation
        shadow1 = _create_round_rect(x1 + 6, y1 + 10, x2 + 6, y2 + 10, card_radius, fill="#000000")
        preview_canvas.itemconfigure(shadow1, stipple="gray50")
        shadow2 = _create_round_rect(x1 + 2, y1 + 4, x2 + 2, y2 + 4, card_radius, fill="#000000")
        preview_canvas.itemconfigure(shadow2, stipple="gray25")

        _create_round_rect(x1, y1, x2, y2, card_radius, fill=card_bg_hex)

        cover_x1 = x1 + pad_x
        cover_y1 = y1 + pad_y
        cover_x2 = cover_x1 + cover_size
        cover_y2 = cover_y1 + cover_size

        cover_bg_rgb = _blend(card_bg_rgb, (255, 255, 255), 0.08)
        _create_round_rect(cover_x1, cover_y1, cover_x2, cover_y2, cover_radius, fill=_rgb_to_hex(cover_bg_rgb))

        # Determine cover content
        state = (preview_state_var.get() or "Playing").strip().lower()
        placeholder_variant = (placeholder_value_var.get() or "dark").strip().lower()
        if placeholder_variant in {"off", "none", "false", "0"}:
            placeholder_variant = "off"
        use_placeholder = state.startswith("nothing")

        img: Optional[tk.PhotoImage] = None
        if use_placeholder and placeholder_variant in {"dark", "light"}:
            img = _get_placeholder_image(placeholder_variant, cover_size)

        cx = int((cover_x1 + cover_x2) / 2)
        cy = int((cover_y1 + cover_y2) / 2)
        if img is not None:
            preview_canvas.create_image(cx, cy, image=img)
            placeholder_preview_state["last"] = img
        else:
            note_rgb = _blend(card_bg_rgb, text_rgb, 0.6)
            try:
                note_font = tkfont.Font(family=font_family, size=max(14, cover_size // 3), weight="bold")
            except Exception:  # pylint: disable=broad-except
                note_font = (FONT, max(14, cover_size // 3), "bold")
            preview_canvas.create_text(cx, cy, text="♪", fill=_rgb_to_hex(note_rgb), font=note_font)

        # Text
        text_x = cover_x2 + card_gap
        title_y = cover_y1
        artist_y = title_y + title_size + title_artist_gap

        title_text = "Song Title" if not state.startswith("nothing") else "Nothing playing"
        artist_text = "Artist Name" if not state.startswith("nothing") else ""

        try:
            title_font = tkfont.Font(family=font_family, size=title_size, weight="bold")
            artist_font = tkfont.Font(family=font_family, size=artist_size)
            time_font = tkfont.Font(family=font_family, size=time_size)
        except Exception:  # pylint: disable=broad-except
            title_font = (FONT, title_size, "bold")
            artist_font = (FONT, artist_size)
            time_font = (FONT, time_size)

        preview_canvas.create_text(text_x, title_y, anchor="nw", text=title_text, fill=_rgb_to_hex(text_rgb), font=title_font)
        if artist_text:
            preview_canvas.create_text(text_x, artist_y, anchor="nw", text=artist_text, fill=_rgb_to_hex(artist_rgb), font=artist_font)

        if show_progress_preview:
            track_y = artist_y + artist_size + 12
            track_x1 = text_x
            track_x2 = text_x + info_w
            track_y1 = track_y
            track_y2 = track_y + progress_height
            _create_round_rect(int(track_x1), int(track_y1), int(track_x2), int(track_y2), 999, fill=track_hex)

            # Gradient fill (approx)
            fill_w = int(info_w * 0.65)
            steps = 28
            for i in range(steps):
                t = i / max(1, steps - 1)
                c = _blend(accent_start_rgb, accent_end_rgb, t)
                seg_x1 = int(track_x1 + (fill_w * i) / steps)
                seg_x2 = int(track_x1 + (fill_w * (i + 1)) / steps)
                preview_canvas.create_rectangle(seg_x1, int(track_y1), seg_x2, int(track_y2), outline="", fill=_rgb_to_hex(c))

            time_y = track_y2 + 8
            preview_canvas.create_text(
                text_x,
                time_y,
                anchor="nw",
                text="1:27 / 4:05",
                fill=_rgb_to_hex(_blend(card_bg_rgb, text_rgb, 0.75)),
                font=time_font,
            )

    for var in (
        preview_state_var,
        placeholder_value_var,
        theme_font_var,
        theme_text_color_var,
        theme_card_bg_var,
        theme_card_radius_var,
        theme_accent_start_var,
        theme_accent_end_var,
        theme_cover_size_var,
        theme_min_width_var,
        theme_title_size_var,
        theme_artist_size_var,
    ):
        var.trace_add("write", _schedule_preview_redraw)

    progress_var.trace_add("write", _schedule_preview_redraw)
    preview_canvas.bind("<Configure>", _schedule_preview_redraw)
    _schedule_preview_redraw()

    def on_detect_api_version() -> None:
        url = url_var.get().strip().rstrip("/")
        if not (url.startswith("http://") or url.startswith("https://")):
            set_status("Navidrome URL must start with http:// or https://", kind="error")
            return
        if not user_var.get().strip():
            set_status("Username is required", kind="error")
            return
        if not pass_var.get().strip():
            set_status("Password is required", kind="error")
            return
        try:
            timeout_i = int(float(timeout_var.get().strip() or "6"))
        except ValueError:
            set_status("Timeout must be a number", kind="error")
            return

        set_status("Detecting API version…", kind="working")
        root.update_idletasks()
        try:
            detected = detect_subsonic_api_version(
                navidrome_url=url,
                navidrome_user=user_var.get().strip(),
                navidrome_password=pass_var.get().strip(),
                navidrome_client=(client_var.get().strip() or "obs-overlay"),
                timeout=float(timeout_i),
            )
        except Exception as exc:  # pylint: disable=broad-except
            set_status(f"Detect failed: {type(exc).__name__}: {exc}", kind="error")
            return

        version_var.set(detected)
        set_status(f"Detected API version: {detected}", kind="ok")

    # API version field + inline Detect button
    add_field_with_button(
        nav_body,
        2,
        1,
        "API version",
        version_var,
        button_text="Detect",
        command=on_detect_api_version,
    )

    add_field(nav_body, 3, 0, "Timeout (sec)", timeout_var, colspan=2)
    tk.Label(
        nav_body,
        text="Tip: URL is usually http://localhost:4533 (or your server IP).",
        bg=SURFACE,
        fg=TEXT_MUTED,
        font=(FONT, 9),
        anchor="w",
    ).grid(row=8, column=0, columnspan=2, sticky="w")

    add_field(overlay_body, 0, 0, "Overlay host", host_var)
    add_field(overlay_body, 0, 1, "Overlay port", port_var)
    add_field(overlay_body, 1, 0, "Refresh (sec)", refresh_var)

    def on_placeholder_label_change(*_args: object) -> None:
        label = placeholder_label_var.get()
        if label in PLACEHOLDER_OPTIONS:
            placeholder_value_var.set(PLACEHOLDER_OPTIONS[label])

    placeholder_label_var.trace_add("write", on_placeholder_label_change)

    add_dropdown(
        overlay_body,
        1,
        1,
        "When nothing playing",
        placeholder_label_var,
        options=list(PLACEHOLDER_OPTIONS.keys()),
    )

    progress_checkbox = tk.Checkbutton(
        overlay_body,
        text="Show progress bar + time",
        variable=progress_var,
        bg=SURFACE,
        fg=TEXT,
        activebackground=SURFACE,
        activeforeground=TEXT,
        selectcolor=SURFACE,
        font=(FONT, 10),
        cursor="hand2",
    )
    progress_checkbox.grid(row=4, column=0, columnspan=2, sticky="w", pady=(0, 0))

    def on_font_preset_change(*_args: object) -> None:
        label = theme_font_preset_var.get()
        if label in FONT_PRESETS:
            theme_font_var.set(FONT_PRESETS[label])

    theme_font_preset_var.trace_add("write", on_font_preset_change)

    add_dropdown(
        theme_body,
        0,
        0,
        "Font preset",
        theme_font_preset_var,
        options=list(FONT_PRESETS.keys()) + ["Custom…"],
    )
    add_field(theme_body, 0, 1, "Font family (CSS)", theme_font_var)

    text_color_entry = add_field(theme_body, 1, 0, "Text color", theme_text_color_var)
    enable_color_picker_on_click(text_color_entry, theme_text_color_var)

    card_bg_entry = add_field(theme_body, 1, 1, "Card background", theme_card_bg_var)
    enable_color_picker_on_click(
        card_bg_entry,
        theme_card_bg_var,
        prefer_rgba_alpha_from=theme_card_bg_var,
    )

    accent_start_entry = add_field(theme_body, 2, 0, "Accent start", theme_accent_start_var)
    enable_color_picker_on_click(accent_start_entry, theme_accent_start_var)

    accent_end_entry = add_field(theme_body, 2, 1, "Accent end", theme_accent_end_var)
    enable_color_picker_on_click(accent_end_entry, theme_accent_end_var)

    add_field(theme_body, 3, 0, "Card radius (px)", theme_card_radius_var)
    add_field(theme_body, 3, 1, "Cover size (px)", theme_cover_size_var)
    add_field(theme_body, 4, 0, "Min width (px)", theme_min_width_var)
    add_field(theme_body, 4, 1, "Title size (px)", theme_title_size_var)
    add_field(theme_body, 5, 0, "Artist size (px)", theme_artist_size_var)

    tk.Label(
        theme_body,
        text="Tip: Leave a field blank to remove it from .env (defaults apply).",
        bg=SURFACE,
        fg=TEXT_MUTED,
        font=(FONT, 9),
        anchor="w",
    ).grid(row=12, column=0, columnspan=2, sticky="w", pady=(4, 0))

    def validate_inputs() -> tuple[Optional[str], Optional[dict[str, str]]]:
        url = url_var.get().strip().rstrip("/")
        if not (url.startswith("http://") or url.startswith("https://")):
            return "Navidrome URL must start with http:// or https://", None
        if not user_var.get().strip():
            return "Username is required", None
        if not pass_var.get().strip():
            return "Password is required", None
        try:
            timeout_i = int(float(timeout_var.get().strip() or "6"))
            port_i = int(port_var.get().strip() or "8080")
            refresh_i = int(refresh_var.get().strip() or "1")
        except ValueError:
            return "Timeout/Port/Refresh must be numbers", None
        if port_i < 1 or port_i > 65535:
            return "Overlay port must be between 1 and 65535", None
        if refresh_i < 1 or refresh_i > 60:
            return "Refresh must be between 1 and 60 seconds", None

        def parse_optional_int(
            raw: str, *, field: str, minimum: int, maximum: int
        ) -> tuple[Optional[str], Optional[int]]:
            cleaned = raw.strip()
            if not cleaned:
                return None, None
            try:
                value = int(cleaned)
            except ValueError:
                return f"{field} must be a number", None
            if value < minimum or value > maximum:
                return f"{field} must be between {minimum} and {maximum}", None
            return None, value

        err, card_radius_i = parse_optional_int(
            theme_card_radius_var.get(), field="Card radius", minimum=0, maximum=128
        )
        if err:
            return err, None
        err, cover_size_i = parse_optional_int(
            theme_cover_size_var.get(), field="Cover size", minimum=16, maximum=512
        )
        if err:
            return err, None
        err, min_width_i = parse_optional_int(
            theme_min_width_var.get(), field="Min width", minimum=100, maximum=2000
        )
        if err:
            return err, None
        err, title_size_i = parse_optional_int(
            theme_title_size_var.get(), field="Title size", minimum=8, maximum=72
        )
        if err:
            return err, None
        err, artist_size_i = parse_optional_int(
            theme_artist_size_var.get(), field="Artist size", minimum=8, maximum=72
        )
        if err:
            return err, None

        values: dict[str, str] = {
            "NAVIDROME_URL": url,
            "NAVIDROME_USER": user_var.get().strip(),
            "NAVIDROME_PASSWORD": pass_var.get().strip(),
            "NAVIDROME_CLIENT_NAME": client_var.get().strip() or "obs-overlay",
            "NAVIDROME_API_VERSION": version_var.get().strip() or "1.16.1",
            "NAVIDROME_TIMEOUT": str(timeout_i),
            "OVERLAY_HOST": host_var.get().strip() or "127.0.0.1",
            "OVERLAY_PORT": str(port_i),
            "OVERLAY_REFRESH_SECONDS": str(refresh_i),
            "OVERLAY_SHOW_PROGRESS": "true" if progress_var.get() else "false",
            "OVERLAY_NOTHING_PLAYING_PLACEHOLDER": placeholder_value_var.get().strip().lower() or "dark",
        }

        # Theme values are optional; if blank, omit them from .env.
        if theme_font_var.get().strip():
            values["OVERLAY_THEME_FONT_FAMILY"] = theme_font_var.get().strip()
        if theme_text_color_var.get().strip():
            values["OVERLAY_THEME_TEXT_COLOR"] = theme_text_color_var.get().strip()
        if theme_card_bg_var.get().strip():
            values["OVERLAY_THEME_CARD_BG"] = theme_card_bg_var.get().strip()
        if card_radius_i is not None:
            values["OVERLAY_THEME_CARD_RADIUS_PX"] = str(card_radius_i)
        if theme_accent_start_var.get().strip():
            values["OVERLAY_THEME_ACCENT_START"] = theme_accent_start_var.get().strip()
        if theme_accent_end_var.get().strip():
            values["OVERLAY_THEME_ACCENT_END"] = theme_accent_end_var.get().strip()
        if cover_size_i is not None:
            values["OVERLAY_THEME_COVER_SIZE_PX"] = str(cover_size_i)
        if min_width_i is not None:
            values["OVERLAY_THEME_CARD_MIN_WIDTH_PX"] = str(min_width_i)
        if title_size_i is not None:
            values["OVERLAY_THEME_TITLE_SIZE_PX"] = str(title_size_i)
        if artist_size_i is not None:
            values["OVERLAY_THEME_ARTIST_SIZE_PX"] = str(artist_size_i)
        return None, values

    def validate_and_save() -> Optional[str]:
        err, values = validate_inputs()
        if err:
            return err
        assert values is not None
        write_env_file(env_path, values)
        return None

    def on_test_connection() -> None:
        err, values = validate_inputs()
        if err:
            set_status(err, kind="error")
            return
        assert values is not None

        set_status("Testing connection…", kind="working")
        root.update_idletasks()
        try:
            config = load_config(env_path, overrides=values)
            _ = fetch_now_playing(config)
        except Exception as exc:  # pylint: disable=broad-except
            set_status(f"Connection failed: {type(exc).__name__}: {exc}", kind="error")
            return

        set_status("Connection OK.", kind="ok")

    def on_save(start: bool) -> None:
        err = validate_and_save()
        if err:
            messagebox.showerror("Invalid settings", err)
            return
        start_choice["start"] = start
        root.destroy()

    # Wire header actions now that handlers exist.
    header_test_button.configure(command=on_test_connection)
    header_save_button.configure(command=lambda: on_save(False))
    header_start_button.configure(command=lambda: on_save(True))

    # Helpful ergonomics
    url_entry.focus_set()
    root.bind("<Escape>", lambda _event: root.destroy())

    root.mainloop()
    return start_choice["start"]
