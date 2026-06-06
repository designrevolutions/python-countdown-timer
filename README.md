# Python Countdown Timer

I built this because the countdown timer built into Windows is genuinely terrible. It's buried inside the Clock app, can't be resized, can't go fullscreen, and the digits are tiny — useless if you're running a session or presentation and need the room to see the clock on a screen.

This one does what I actually need: big digits that fill the window, proper fullscreen support, a configurable warning colour when time is running low, and a settings block at the top of the file so everything is in one place and easy to change.

## Features

- Digits auto-scale to fill whatever size window you give it
- Fullscreen / windowed toggle (borderless fullscreen, no title bar)
- Warning colour when time drops below a threshold (default: last 60 seconds)
- Pause, Resume, and Reset controls
- Alarm sound when the countdown hits zero — plays a `.wav` file if you point it at one, falls back to a system beep otherwise
- Optional transparent background
- Always-on-top mode
- All configuration in a single `SETTINGS` block at the top of `timer.py`

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

## Keyboard shortcuts

| Key | Action |
|---|---|
| `Space` | Start / Pause / Resume |
| `R` | Reset |
| `Escape` | Exit fullscreen |

## Requirements

- Python 3.10+
- `pygame>=2.5.0` — optional, for `.wav`/`.mp3` alarm files
