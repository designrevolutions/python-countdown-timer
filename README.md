# Python Countdown Timer

I built this because the countdown timer built into Windows is genuinely terrible. It's buried inside the Clock app, can't be resized, can't go fullscreen, and the digits are tiny — useless if you're running a session or presentation and need the room to see the clock on a screen.

This one does what I actually need: big digits that fill the window, proper fullscreen support, a configurable warning colour when time is running low, and a settings block at the top of the file so everything is in one place and easy to change.

## Features

- Digits auto-scale to fill whatever size window you give it
- Fullscreen / windowed toggle (borderless fullscreen, no title bar)
- Warning colour when time drops below a threshold (default: last 60 seconds)
- Pause, Resume, and Reset controls
- Alarm sound when the countdown hits zero — plays a `.wav` file if you point it at one, falls back to a system beep otherwise
- Optional transparent background (Windows and macOS)
- Always-on-top mode
- All configuration in a single `SETTINGS` block at the top of `timer.py`
- Command-line arguments to override any setting without editing the file

## Setup

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate

# Optional: only needed if you want to play a .wav/.mp3 alarm file
pip install pygame

python timer.py
```

No external packages are required if you're happy with the built-in system beep.

## Configuration

Open `timer.py` and edit the `SETTINGS` block near the top. Every option is commented.

| Setting | Default | What it does |
|---|---|---|
| `COUNTDOWN_MINUTES` | `45` | Starting minutes |
| `COUNTDOWN_SECONDS` | `0` | Starting seconds |
| `FONT_FAMILY` | `"Helvetica"` | Font used for the digits |
| `FONT_SIZE` | `None` | `None` = auto-scale; set an integer to lock the size |
| `TEXT_COLOR` | `"#FFFFFF"` | Digit colour |
| `BACKGROUND_COLOR` | `"#000000"` | Window background |
| `WARNING_COLOR` | `"#FF4444"` | Digit colour in the final countdown |
| `WARNING_THRESHOLD_SECONDS` | `60` | When the warning colour activates |
| `TRANSPARENT_BACKGROUND` | `False` | See-through window background |
| `ALARM_SOUND_FILE` | `""` | Path to a `.wav` file; leave empty for system beep |
| `ALARM_DURATION_SECONDS` | `3` | How long to play the alarm file |
| `BUTTON_FONT_SIZE` | `14` | Size of the control buttons |
| `ALWAYS_ON_TOP` | `False` | Float the window above everything else |

## Command-line usage

All settings can be passed as arguments so you don't need to edit the file each time. Anything not supplied falls back to the `SETTINGS` block defaults.

```
py timer.py --time 25
py timer.py --time 1.5                      # 1 min 30 sec (decimals work)
py timer.py --time 45 -s 30                 # 45 min 30 sec
py timer.py --time 10 --top                 # always on top
py timer.py --time 25 --fullscreen          # start in fullscreen
py timer.py --time 5  --transparent         # transparent background
py timer.py --time 10 --bg "#1a1a2e" --fg "#e94560"
py timer.py --time 5  --font "Courier New" --font-size 120
py timer.py --time 20 --alarm alarm.wav
py timer.py --help                          # full reference
```

| Argument | Short | What it does |
|---|---|---|
| `--time MINS` | `-t` | Duration in minutes; decimals allowed (`1.5` = 1m30s) |
| `--seconds S` | `-s` | Extra seconds added on top of `--time` |
| `--bg HEX` | | Background colour e.g. `"#000000"` |
| `--fg HEX` | | Digit colour e.g. `"#FFFFFF"` |
| `--warning-color HEX` | | Colour used in the warning period |
| `--warning SECS` | | Seconds at which warning colour activates |
| `--font NAME` | | Font family e.g. `"Courier New"` |
| `--font-size PT` | | Lock font size in points (omit for auto-scale) |
| `--alarm FILE` | | Path to `.wav` alarm file |
| `--top` | | Keep window above all other windows |
| `--fullscreen` | | Start in fullscreen immediately |
| `--transparent` | | Transparent background |

Boolean flags (`--top`, `--fullscreen`, `--transparent`) are either present or absent — no `=True` needed.

## Keyboard shortcuts

| Key | Action |
|---|---|
| `Space` | Start / Pause / Resume |
| `R` | Reset |
| `Escape` | Exit fullscreen |

## Requirements

- Python 3.10+
- `pygame>=2.5.0` — optional, for `.wav`/`.mp3` alarm files
