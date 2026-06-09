# =============================================================================
#  SETUP INSTRUCTIONS
# =============================================================================
#
#  Python version recommended: 3.10 or newer
#  All core features use the standard library only (no pip install required).
#
#  1. Create a virtual environment
#       python -m venv venv
#
#  2. Activate it
#       Windows:      venv\Scripts\activate
#       macOS/Linux:  source venv/bin/activate
#
#  3. Install optional dependency (only needed for .wav/.mp3 alarm files)
#
#       Recommended (best cross-platform audio support):
#         pip install pygame
#
#       Lightweight alternative (.wav only; known issues on Python 3.10+):
#         pip install playsound
#
#       If you only want the built-in system beep, skip step 3 entirely.
#
#  4. Run the timer
#
#       Basic launch (shows a console window alongside the timer):
#         python timer.py
#
#       Clean launch on Windows (no console window, GUI only):
#         pythonw timer.py
#
#       Pass --help to see all available options:
#         python timer.py --help
#
#  ── Command-line examples ─────────────────────────────────────────────────
#
#    Set the timer to 25 minutes:
#      python timer.py --time 25
#
#    Set 45 minutes and 30 seconds:
#      python timer.py --time 45 --seconds 30
#
#    Decimals work too (1.5 = 1 min 30 sec):
#      python timer.py --time 1.5
#
#    Custom colours:
#      python timer.py --time 10 --bg "#1a1a2e" --fg "#e94560"
#
#    Custom font and size:
#      python timer.py --time 5 --font "Courier New" --font-size 120
#
#    Boolean flags — just add them, no value needed:
#      python timer.py --time 25 --top               # always on top
#      python timer.py --time 25 --fullscreen        # start fullscreen
#      python timer.py --time 25 --transparent       # transparent background
#
#    Point at an alarm sound file:
#      python timer.py --time 20 --alarm "C:\sounds\alarm.wav"
#
#    Combine anything:
#      pythonw timer.py --time 25 --top --fullscreen --bg "#000000"
#
#    Note: any argument not supplied falls back to the SETTINGS block below.
#
#  ── requirements.txt (copy this block into a file named requirements.txt) ─
#
#     # Uncomment one line to enable alarm sound-file support:
#     # pygame>=2.5.0          # recommended — .wav and .mp3, all platforms
#     # playsound>=1.3.0       # alternative — .wav only, less reliable on 3.10+
#
#  ─────────────────────────────────────────────────────────────────────────
#
#  Keyboard shortcuts (when window is focused):
#    Space   — start / pause / resume
#    R       — reset
#    Escape  — exit fullscreen
#
# =============================================================================

import argparse
import os
import sys
import time
import platform
import threading
import tkinter as tk
from tkinter import font as tkfont

# ── Optional audio back-ends (soft dependencies) ─────────────────────────────
try:
    import pygame as _pygame
    _PYGAME = True
except ImportError:
    _PYGAME = False

try:
    from playsound import playsound as _playsound
    _PLAYSOUND = True
except ImportError:
    _PLAYSOUND = False


# =============================================================================
#  SETTINGS  —  edit this block to configure the timer
# =============================================================================

# ── Duration ──────────────────────────────────────────────────────────────────

# Starting countdown value; COUNTDOWN_MINUTES may exceed 59 (e.g. 90 for 1h30m)
COUNTDOWN_MINUTES = 45
COUNTDOWN_SECONDS = 0

# ── Typography ────────────────────────────────────────────────────────────────

# Font family for the timer digits and control buttons
FONT_FAMILY = "Helvetica"

# Timer digit size.
#   None  → auto-scales to fill the window; updates on every resize.
#   int   → fixed size (e.g. 120); window size has no effect on digit size.
FONT_SIZE = None

# ── Colours ───────────────────────────────────────────────────────────────────

# Colour of the countdown digits during normal operation
TEXT_COLOR = "#FFFFFF"

# Window background colour
BACKGROUND_COLOR = "#000000"

# Colour the digits turn when remaining seconds fall below the warning threshold
WARNING_COLOR = "#FF4444"

# Seconds at which the warning colour activates (e.g. 120 = last 2 minutes)
WARNING_THRESHOLD_SECONDS = 120

# ── Window transparency ───────────────────────────────────────────────────────
# When True, attempts to make BACKGROUND_COLOR pixels transparent so the
# desktop shows through.
#
#   Windows — uses -transparentcolor.  Every pixel that exactly matches
#             BACKGROUND_COLOR becomes transparent, including any fringe pixels
#             from text anti-aliasing.  Tip: use a slightly non-black colour
#             such as "#010101" so pure-black text edges remain visible.
#   macOS   — uses the -transparent attribute; the OS handles compositing.
#   Linux   — requires a compositing window manager (e.g. Picom).  If the WM
#             does not support it the setting is silently ignored.
TRANSPARENT_BACKGROUND = True

# ── Alarm ─────────────────────────────────────────────────────────────────────

# Path to an audio file played when the countdown reaches zero.
# Leave as "" to skip file playback and fall back to the platform system beep.
# Absolute paths are safest; relative paths are resolved from the working dir.
#   Examples:
#     Windows  →  r"C:\Users\you\sounds\alarm.wav"
#     macOS    →  "/Users/you/sounds/alarm.wav"
ALARM_SOUND_FILE = ""

# How long (seconds) to keep the alarm file playing before stopping it.
# Has no effect on the system-beep fallback, which has its own fixed duration.
ALARM_DURATION_SECONDS = 30

# ── Buttons ───────────────────────────────────────────────────────────────────

# Font size used by the Fullscreen / Start / Reset buttons
BUTTON_FONT_SIZE = 14

# ── Window behaviour ─────────────────────────────────────────────────────────

# Keep the timer window on top of all other application windows
ALWAYS_ON_TOP = False

# Start in fullscreen immediately on launch
START_FULLSCREEN = False

# =============================================================================


class CountdownTimer(tk.Tk):
    """Single-window countdown timer with dynamic font scaling."""

    # ms to wait after the last resize event before recalculating font size;
    # prevents thrashing while the user is actively dragging the window edge
    _RESIZE_DEBOUNCE_MS = 60

    # Polling interval (ms) for the wall-clock tick; small enough that the
    # display never lags more than this behind the actual second boundary
    _TICK_INTERVAL_MS = 100

    def __init__(self) -> None:
        super().__init__()

        self._total: int = COUNTDOWN_MINUTES * 60 + COUNTDOWN_SECONDS
        self._left:  int = self._total   # seconds currently shown

        self._running         = False
        self._fullscreen      = False
        self._flashing        = False
        self._flash_on        = False
        self._transparency_on = False  # toggled by _apply_transparency / _toggle_bg

        # Wall-clock anchors used for drift-free timing
        self._anchor_mono:  float = 0.0  # time.monotonic() when (re)started
        self._anchor_left:  int   = 0    # self._left at that moment

        # tkinter after() handle IDs — None means not currently scheduled
        self._tick_id:   int | None = None
        self._flash_id:  int | None = None
        self._resize_id: int | None = None

        self._setup_window() # This fn is there to configure the window title, size, and always-on-top behaviour
        self._build_ui() # This fn is there to create and arrange the timer label and control buttons
        # These 2 fns are just standard tkinter setup. This is standard boilerplate code for creating a tkinter application window and adding widgets to it.

        if TRANSPARENT_BACKGROUND:
            self._apply_transparency() # This fn is there to set up the window transparency based on the TRANSPARENT_BACKGROUND setting and the platform. It uses different methods for Windows, macOS, and Linux.

        self.bind("<Configure>", self._on_configure)
        self.bind("<Escape>",    lambda _e: self._exit_fullscreen())
        self.bind("<space>",     lambda _e: self._toggle_pause())
        self.bind("r",           lambda _e: self._reset())
        self.bind("R",           lambda _e: self._reset())

        self._refresh_label()

        if START_FULLSCREEN:
            self.after(200, self._enter_fullscreen)

    # ── Window setup ──────────────────────────────────────────────────────────

    def _setup_window(self) -> None:
        self.title("Countdown Timer")
        self.configure(bg=BACKGROUND_COLOR)
        self.attributes("-topmost", ALWAYS_ON_TOP)
        self.geometry("800x520")
        self.minsize(320, 220)

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self) -> None:

        # +++++++++++++++++++++++++++++++
        # Setup of countdown timer display. Start
        # Timer display — expands to fill all available vertical space

        # Setup the outer canvas frame, which contains the countdown timer - the buttons below are inside another object.
        self._canvas = tk.Frame(self, bg=BACKGROUND_COLOR)
        self._canvas.pack(fill=tk.BOTH, expand=True)

        self._label = tk.Label(
            self._canvas,
            text=self._fmt(self._left),
            font=(FONT_FAMILY, FONT_SIZE or 72),
            fg=TEXT_COLOR,
            bg=BACKGROUND_COLOR,
            anchor="center",
        )
        self._label.pack(fill=tk.BOTH, expand=True)

        # Setup of countdown timer display. End
        # +++++++++++++++++++++++++++++++

        # >>>>>>>>>>>>>>>>>>>>
        # Setup of buttons start
        # Button row — sits below the timer label
        bar = tk.Frame(self, bg=BACKGROUND_COLOR) # This is the container for the control buttons. It is placed at the bottom of the window, below the timer label. The buttons themselves will be added to an inner frame within this bar, which allows them to be centered regardless of the window width.
        bar.pack(fill=tk.X, pady=(0, 14))
        self._bar = bar  # keep a reference for transparency

        # Inner frame so buttons are centred regardless of window width
        inner = tk.Frame(bar, bg=BACKGROUND_COLOR)
        self._inner = inner
        inner.pack()  # default anchor=CENTER centres it horizontally

        _btn_kw = dict(
            font=(FONT_FAMILY, BUTTON_FONT_SIZE),
            bg="#2d2d2d",
            fg="#eeeeee",
            activebackground="#505050",
            activeforeground="#ffffff",
            relief=tk.FLAT,
            padx=20,
            pady=7,
            cursor="hand2",
            bd=0,
        )
        self._btn_fs    = tk.Button(inner, text="Fullscreen", command=self._toggle_fullscreen, **_btn_kw)
        self._btn_start = tk.Button(inner, text="Start",      command=self._toggle_pause,      **_btn_kw)
        self._btn_reset = tk.Button(inner, text="Reset",      command=self._reset,             **_btn_kw)

        for btn in (self._btn_fs, self._btn_start, self._btn_reset):
            btn.pack(side=tk.LEFT, padx=6)

        # Extra buttons only present when transparent mode is active on Windows,
        # because overrideredirect removes the system title bar and taskbar entry.
        if TRANSPARENT_BACKGROUND and platform.system() == "Windows":
            # Toggle lets the user temporarily make the window solid so they can
            # move it with Shift+Win+Arrow or alt-tab, then re-enable transparency.
            self._btn_trans = tk.Button(
                inner, text="Show BG",
                command=self._toggle_bg, **_btn_kw,
            )
            self._btn_trans.pack(side=tk.LEFT, padx=6)

            self._btn_close = tk.Button(
                inner, text="✕", command=self.destroy,
                **{**_btn_kw, "padx": 12, "fg": "#ff6b6b"},
            )
            self._btn_close.pack(side=tk.LEFT, padx=6)

        # Setup of buttons end
        # >>>>>>>>>>>>>>>>>>>>

    # ── Formatting helper ─────────────────────────────────────────────────────

    @staticmethod
    def _fmt(seconds: int) -> str:
        """Return HH:MM:SS when hours > 0, else MM:SS."""
        seconds = max(0, int(seconds))
        h, r = divmod(seconds, 3600)
        m, s = divmod(r, 60)
        return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"

    def _digit_color(self) -> str:
        if 0 < self._left <= WARNING_THRESHOLD_SECONDS:
            return WARNING_COLOR
        return TEXT_COLOR

    # ── Font scaling ──────────────────────────────────────────────────────────
## Stopped here
    def _on_configure(self, event: tk.Event) -> None:
        """Debounce resize events before recalculating font size."""
        if event.widget is not self:
            return
        if self._resize_id is not None:
            self.after_cancel(self._resize_id)
        self._resize_id = self.after(self._RESIZE_DEBOUNCE_MS, self._scale_font)

    def _scale_font(self) -> None:
        """Binary-search for the largest font that fits inside the canvas."""
        self._resize_id = None
        if FONT_SIZE is not None:
            return  # user has pinned the size; nothing to do

        text = self._label.cget("text")
        w    = self._canvas.winfo_width()
        h    = self._canvas.winfo_height()
        if w < 30 or h < 30:
            return  # window not yet drawn

        # Search space: 8 pt up to the larger canvas dimension (generous ceiling)
        lo, hi, best = 8, max(w, h), 8
        while lo <= hi:
            mid = (lo + hi) // 2
            f   = tkfont.Font(family=FONT_FAMILY, size=mid)
            fits = f.measure(text) <= w * 0.92 and f.metrics("linespace") <= h * 0.85
            if fits:
                best = mid
                lo   = mid + 1
            else:
                hi   = mid - 1

        self._label.configure(font=(FONT_FAMILY, best))

    # ── Countdown tick (wall-clock based to avoid drift) ─────────────────────

    def _tick(self) -> None:
        if not self._running:
            return
        elapsed      = time.monotonic() - self._anchor_mono
        self._left   = max(0, self._anchor_left - int(elapsed))
        self._refresh_label()
        if self._left > 0:
            self._tick_id = self.after(self._TICK_INTERVAL_MS, self._tick)
        else:
            self._running = False
            self._time_up()

    def _refresh_label(self) -> None:
        """Update the timer label text and colour."""
        self._label.configure(
            text=self._fmt(self._left),
            fg=self._digit_color(),
            bg=BACKGROUND_COLOR,
        )
        self._scale_font()

    # ── Controls ─────────────────────────────────────────────────────────────

    def _toggle_pause(self) -> None:
        """Start → Pause → Resume cycle."""
        if self._left == 0:
            return
        if self._running:
            # Pause: freeze the remaining-seconds snapshot
            self._running = False
            if self._tick_id is not None:
                self.after_cancel(self._tick_id)
                self._tick_id = None
            self._btn_start.configure(text="Resume")
        else:
            # Start or Resume: anchor wall-clock to current remaining seconds
            self._running          = True
            self._anchor_mono      = time.monotonic()
            self._anchor_left      = self._left
            self._btn_start.configure(text="Pause")
            self._tick()

    def _reset(self) -> None:
        """Stop the timer, cancel any animation, and restore the original time."""
        self._running = False
        if self._tick_id is not None:
            self.after_cancel(self._tick_id)
            self._tick_id = None
        self._stop_flash()
        self._left = self._total
        self._btn_start.configure(text="Start", state=tk.NORMAL)
        self._refresh_label()

    # ── Fullscreen toggle ─────────────────────────────────────────────────────

    def _toggle_fullscreen(self) -> None:
        if self._fullscreen:
            self._exit_fullscreen()
        else:
            self._enter_fullscreen()

    def _enter_fullscreen(self) -> None:
        """Switch to borderless fullscreen."""
        self._fullscreen = True
        if TRANSPARENT_BACKGROUND and platform.system() == "Windows":
            # overrideredirect conflicts with -fullscreen at the WinAPI level;
            # manually stretch the window to cover the screen instead.
            self._pre_fs_geometry = self.geometry()
            sw = self.winfo_screenwidth()
            sh = self.winfo_screenheight()
            self.geometry(f"{sw}x{sh}+0+0")
        else:
            self.attributes("-fullscreen", True)
        self._btn_fs.configure(text="Windowed")

    def _exit_fullscreen(self) -> None:
        """Restore windowed size."""
        if not self._fullscreen:
            return
        self._fullscreen = False
        if TRANSPARENT_BACKGROUND and platform.system() == "Windows":
            self.geometry(getattr(self, "_pre_fs_geometry", "800x520"))
        else:
            self.attributes("-fullscreen", False)
        self._btn_fs.configure(text="Fullscreen")

    # ── Time's Up ─────────────────────────────────────────────────────────────

    def _time_up(self) -> None:
        self._label.configure(text="Time's Up!", fg=WARNING_COLOR)
        self._scale_font()                          # rescale for new text length
        self._btn_start.configure(state=tk.DISABLED)
        self._start_flash()
        threading.Thread(target=self._play_alarm, daemon=True).start()

    # ── Flash animation ───────────────────────────────────────────────────────

    def _start_flash(self) -> None:
        self._flashing = True
        self._flash_on = False
        self._flash_cycle()

    def _flash_cycle(self) -> None:
        if not self._flashing:
            return
        self._flash_on = not self._flash_on
        self._label.configure(fg=WARNING_COLOR if self._flash_on else BACKGROUND_COLOR)
        self._flash_id = self.after(500, self._flash_cycle)

    def _stop_flash(self) -> None:
        self._flashing = False
        if self._flash_id is not None:
            self.after_cancel(self._flash_id)
            self._flash_id = None
        # Restore colours so _refresh_label starts from a clean state
        self._label.configure(fg=TEXT_COLOR, bg=BACKGROUND_COLOR)

    # ── Transparency ─────────────────────────────────────────────────────────

    def _apply_transparency(self) -> None:
        system = platform.system()
        if system == "Windows":
            # Remove the system title bar.  Without this, -transparentcolor makes
            # the title bar (also black by default) click-through, so the window
            # can't be moved or closed.  We replace it with drag bindings and a
            # close button added in _build_ui.
            self._transparency_on = True
            self.overrideredirect(True)
            # overrideredirect removes the window from the taskbar, so force
            # topmost so it can't disappear behind other windows.
            self.attributes("-topmost", True)
            self._drag_offset_x = 0
            self._drag_offset_y = 0
            self.bind("<Button-1>",  self._on_drag_start)
            self.bind("<B1-Motion>", self._on_drag_move)
            self.bind("<Alt-F4>",    lambda _: self.destroy())
            self.wm_attributes("-transparentcolor", BACKGROUND_COLOR)
        elif system == "Darwin": # This is for macOS, which identifies as "Darwin"
            self.wm_attributes("-transparent", True)
            for widget in (self, self._canvas, self._label, self._bar, self._inner):
                widget.configure(bg="systemTransparent")
            for btn in (self._btn_fs, self._btn_start, self._btn_reset):
                btn.configure(bg="systemTransparent")
        # Linux: silently skipped; user must configure their compositing WM
        # (e.g. add `blur-background = true;` to picom.conf).

    def _toggle_bg(self) -> None:
        if self._transparency_on:
            self._disable_transparency()
        else:
            self._enable_transparency()

    def _disable_transparency(self) -> None:
        """Make the window solid so Shift+Win+Arrow and alt-tab work normally."""
        self._transparency_on = False
        self._btn_trans.configure(text="Hide BG")
        self.withdraw()
        self.overrideredirect(False)
        self.title("Countdown Timer")
        self.attributes("-topmost", ALWAYS_ON_TOP)
        # Set transparent colour to something that won't match any UI pixel,
        # effectively disabling chroma-key transparency without unsetting it.
        self.wm_attributes("-transparentcolor", "#FEFEFE")
        self.deiconify()

    def _enable_transparency(self) -> None:
        """Restore the transparent floating overlay."""
        self._transparency_on = True
        self._btn_trans.configure(text="Show BG")
        self.withdraw()
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.wm_attributes("-transparentcolor", BACKGROUND_COLOR)
        self.deiconify()

    def _on_drag_start(self, event: tk.Event) -> None:
        """Record where inside the window the user clicked, for drag-to-move."""
        self._drag_offset_x = event.x_root - self.winfo_x()
        self._drag_offset_y = event.y_root - self.winfo_y()

    def _on_drag_move(self, event: tk.Event) -> None:
        """Reposition the window to follow the mouse while Button-1 is held."""
        if self._fullscreen:
            return
        self.geometry(f"+{event.x_root - self._drag_offset_x}+{event.y_root - self._drag_offset_y}")

    # ── Alarm sound ───────────────────────────────────────────────────────────

    def _play_alarm(self) -> None:
        """Play the alarm.  Runs in a daemon thread so the UI stays responsive."""
        path     = (ALARM_SOUND_FILE or "").strip()
        duration = max(0, ALARM_DURATION_SECONDS)

        if path and os.path.isfile(path):
            # ── pygame: best cross-platform choice for .wav and .mp3 ──────────
            if _PYGAME:
                try:
                    _pygame.mixer.init()
                    _pygame.mixer.music.load(path)
                    _pygame.mixer.music.play()
                    time.sleep(duration)
                    _pygame.mixer.music.stop()
                    return
                except Exception:
                    pass  # fall through to next back-end

            # ── playsound: simpler, .wav only, less reliable on 3.10+ ─────────
            if _PLAYSOUND:
                try:
                    _playsound(path)
                    return
                except Exception:
                    pass  # fall through

            # ── winsound: Windows stdlib, .wav only ───────────────────────────
            if platform.system() == "Windows":
                try:
                    import winsound
                    winsound.PlaySound(
                        path,
                        winsound.SND_FILENAME | winsound.SND_ASYNC,
                    )
                    time.sleep(duration)
                    winsound.PlaySound(None, winsound.SND_PURGE)
                    return
                except Exception:
                    pass  # fall through to system beep

        # ── System beep fallback (no external dependencies) ───────────────────
        system = platform.system()
        if system == "Windows":
            try:
                import winsound
                for _ in range(3):
                    winsound.Beep(1000, 400)
                    time.sleep(0.15)
            except Exception:
                pass
        elif system == "Darwin":
            # afplay ships with every macOS installation
            os.system("afplay /System/Library/Sounds/Glass.aiff 2>/dev/null")
        else:
            # Linux: try sox; fall back to the terminal bell character
            played = os.system("play -n -d synth 0.5 sin 880 2>/dev/null") == 0
            if not played:
                sys.stdout.write("\a")
                sys.stdout.flush()


# =============================================================================


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="timer",
        description="Countdown timer. Command-line values override the SETTINGS block.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  py timer.py --time 25\n"
            "  py timer.py --time 1.5                 # 1 min 30 sec\n"
            "  py timer.py --time 45 -s 30            # 45 min 30 sec\n"
            '  py timer.py --time 10 --bg "#1a1a2e" --fg "#e94560"\n'
            '  py timer.py --time 5  --font "Courier New" --font-size 120\n'
            "  py timer.py --time 25 --top --fullscreen\n"
            "  py timer.py --time 20 --alarm alarm.wav\n"
        ),
    )

    # ── Duration ──────────────────────────────────────────────────────────────
    p.add_argument(
        "-t", "--time", type=float, default=None, metavar="MINS",
        help="duration in minutes; decimals allowed (e.g. 1.5 = 1m30s). "
             "Default: COUNTDOWN_MINUTES setting.",
    )
    p.add_argument(
        "-s", "--seconds", type=int, default=None, metavar="S",
        help="extra seconds added on top of --time",
    )

    # ── Appearance ────────────────────────────────────────────────────────────
    a = p.add_argument_group("appearance")
    a.add_argument("--bg",  metavar="HEX", help='background colour  e.g. "#000000"')
    a.add_argument("--fg",  metavar="HEX", help='digit colour  e.g. "#FFFFFF"')
    a.add_argument(
        "--warning-color", metavar="HEX",
        help='colour used during the final warning period  e.g. "#FF4444"',
    )
    a.add_argument(
        "--warning", type=int, metavar="SECS",
        help="seconds remaining when the warning colour activates",
    )
    a.add_argument("--font",      metavar="NAME", help='font family  e.g. "Courier New"')
    a.add_argument("--font-size", type=int, metavar="PT",
                   help="lock digit size in points; omit to auto-scale")

    # ── Behaviour ─────────────────────────────────────────────────────────────
    b = p.add_argument_group("behaviour")
    b.add_argument("--alarm",       metavar="FILE", help="path to alarm sound file (.wav)")
    b.add_argument("--top",         action="store_true", help="keep window on top")
    b.add_argument("--fullscreen",  action="store_true", help="start in fullscreen")
    b.add_argument("--transparent", action="store_true", help="transparent background")

    return p.parse_args()


def _apply_args(args: argparse.Namespace) -> None:
    """Override module-level SETTINGS with values supplied on the command line."""
    global COUNTDOWN_MINUTES, COUNTDOWN_SECONDS
    global FONT_FAMILY, FONT_SIZE
    global TEXT_COLOR, BACKGROUND_COLOR, WARNING_COLOR, WARNING_THRESHOLD_SECONDS
    global ALWAYS_ON_TOP, START_FULLSCREEN, TRANSPARENT_BACKGROUND, ALARM_SOUND_FILE

    if args.time is not None or args.seconds is not None:
        total = int(round((args.time or 0) * 60)) + (args.seconds or 0)
        COUNTDOWN_MINUTES = total // 60
        COUNTDOWN_SECONDS = total % 60

    if args.bg            is not None: BACKGROUND_COLOR          = args.bg
    if args.fg            is not None: TEXT_COLOR                = args.fg
    if args.warning_color is not None: WARNING_COLOR             = args.warning_color
    if args.warning       is not None: WARNING_THRESHOLD_SECONDS = args.warning
    if args.font          is not None: FONT_FAMILY               = args.font
    if args.font_size     is not None: FONT_SIZE                 = args.font_size
    if args.alarm         is not None: ALARM_SOUND_FILE          = args.alarm
    if args.top:                       ALWAYS_ON_TOP             = True
    if args.fullscreen:                START_FULLSCREEN          = True
    if args.transparent:               TRANSPARENT_BACKGROUND    = True


if __name__ == "__main__":
    _apply_args(_parse_args())

    if _PYGAME:
        _pygame.init()

    app = CountdownTimer()
    app.mainloop()
