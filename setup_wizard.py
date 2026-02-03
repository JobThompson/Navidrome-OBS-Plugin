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
        from tkinter import messagebox
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
    root.resizable(False, False)
    root.configure(bg=APP_BG)

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

    def style_primary_button(button: tk.Button) -> None:
        button.configure(
            bg=PRIMARY,
            fg="#ffffff",
            activebackground=PRIMARY_HOVER,
            activeforeground="#ffffff",
            relief="flat",
            bd=0,
            highlightthickness=0,
            font=(FONT, 9, "bold"),
            cursor="hand2",
            padx=14,
            pady=9,
        )

    def style_outlined_button(button: tk.Button) -> None:
        button.configure(
            bg=APP_BG,
            fg=TEXT,
            activebackground="#eeeeee",
            activeforeground=TEXT,
            relief="flat",
            bd=0,
            highlightthickness=1,
            highlightbackground=BORDER,
            highlightcolor=BORDER,
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

    # Layout root
    header = tk.Frame(root, bg=PRIMARY)
    header.grid(row=0, column=0, sticky="ew")
    header.columnconfigure(0, weight=1)
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

    content = tk.Frame(root, bg=APP_BG)
    content.grid(row=1, column=0, sticky="nsew", padx=16, pady=16)
    content.columnconfigure(0, weight=1)

    status_text = tk.StringVar(value="")
    status_label = tk.Label(
        content,
        textvariable=status_text,
        bg=APP_BG,
        fg=TEXT_MUTED,
        anchor="w",
        justify="left",
        font=(FONT, 9),
        wraplength=520,
    )
    status_label.grid(row=0, column=0, sticky="ew", pady=(0, 12))

    nav_card, nav_body = make_card(content, "Navidrome")
    nav_card.grid(row=1, column=0, sticky="ew")

    overlay_card, overlay_body = make_card(content, "Overlay")
    overlay_card.grid(row=2, column=0, sticky="ew", pady=(12, 0))

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
    ):
        var.trace_add("write", clear_status)

    progress_var.trace_add("write", clear_status)

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
        }
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

    actions = tk.Frame(content, bg=APP_BG)
    actions.grid(row=3, column=0, sticky="ew", pady=(14, 0))
    actions.columnconfigure(0, weight=1)

    test_button = tk.Button(actions, text="Test connection", command=on_test_connection)
    style_text_button(test_button)
    test_button.grid(row=0, column=0, sticky="w")

    save_button = tk.Button(actions, text="Save", command=lambda: on_save(False))
    style_outlined_button(save_button)
    save_button.grid(row=0, column=1, sticky="e", padx=(0, 10))

    start_button = tk.Button(actions, text="Save & Start", command=lambda: on_save(True))
    style_primary_button(start_button)
    start_button.grid(row=0, column=2, sticky="e")

    # Helpful ergonomics
    url_entry.focus_set()
    root.bind("<Escape>", lambda _event: root.destroy())

    root.mainloop()
    return start_choice["start"]
