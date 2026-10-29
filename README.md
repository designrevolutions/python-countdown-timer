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
- Quiz pop-up: a random question from `questions.json` appears inside the window once every 5 minutes (see below)
- Quiz stats: every question records how often it was asked and answered right or wrong, shown under the question and in a **Data** report with a chart

## Setup

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate

# Optional: only needed if you want to play a .wav/.mp3 alarm file
pip install pygame

# Required for the quiz pop-up: create your own questions file from the sample
# Windows
copy questions.sample.json questions.json
# macOS / Linux
cp questions.sample.json questions.json

python timer.py
```

No external packages are required if you're happy with the built-in system beep.

**The quiz needs `questions.json`, which is not in the repository.** Only the template `questions.sample.json` is committed. Copy it to `questions.json` as shown above (copying rather than renaming keeps the template intact). `questions.json` is git-ignored because the timer rewrites it as you answer questions. Without it the timer still runs, but no questions appear and **? → Ask now** shows "No quiz questions loaded".

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
| `TRANSPARENT_BACKGROUND` | `True` | See-through window background |
| `START_WITH_BACKGROUND` | `True` | Windows, with transparency on: start solid; the Hide BG button switches to see-through |
| `ALARM_SOUND_FILE` | `""` | Path to a `.wav` file; leave empty for system beep |
| `ALARM_DURATION_SECONDS` | `3` | How long to play the alarm file |
| `BUTTON_FONT_SIZE` | `14` | Size of the control buttons |
| `ALWAYS_ON_TOP` | `False` | Float the window above everything else |
| `START_FULLSCREEN` | `True` | Open in fullscreen (Esc returns to a window) |
| `QUIZ_AUTO_START` | `True` | Pop up quiz questions automatically |
| `QUIZ_INTERVAL_SECONDS` | `300` | Length of each quiz window; one question appears at a random moment within it |
| `QUIZ_TIMEOUT_SECONDS` | `30` | Unanswered questions are dismissed after this long |
| `QUIZ_QUESTIONS_FILE` | `"questions.json"` | Questions file, relative to the project folder |

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

## Quiz pop-up

Once in every 5-minute window, at a random moment, a question flashes up over the timer digits. Type an answer and press Submit (or Enter): a correct answer gets a flashing "Well done!", a nearly-right one shows "Correct, but check the spelling: …" in blue (no flashing), and a wrong one shows the right answer. Unanswered questions disappear after 30 seconds.

The **?** button opens an extra menu row above the main buttons; click **?** again to close it. It holds:

- **Data** — opens the [quiz data report](#quiz-stats-and-the-data-report).
- **Ask now** — shows a question immediately (replacing any question already on screen) and restarts the 5-minute schedule from that moment.

Questions live in `questions.json` (create it from `questions.sample.json`; see [Setup](#setup)), a flat list you can extend:

```json
[
  {"question": "What is the capital of France?", "answer": "Paris", "weight": 20},
  {"question": "What is the capital of Japan?", "answer": "Tokyo", "weight": 20}
]
```

`weight` sets how often a question comes up: its chance of being picked is proportional to its weight, so a question at 40 is twice as likely as one at 20. Every question starts at 20.

- **Wrong answer:** +5, with no upper limit.
- **Correct (or close) answer:** if the weight is above 20 it first drops back to 20, then it goes down by 5, never below 1. A question answered correctly over and over goes 20 → 15 → 10 → 5 → 1, so it still comes up now and then.
- **No answer (timed out):** no change.

Weights are saved back to `questions.json`, so they carry over between sessions. You can leave `weight` out when adding questions; it starts at 20. The values are set by `DEFAULT_WEIGHT`, `MIN_WEIGHT`, `WEIGHT_UP` and `WEIGHT_DOWN` at the top of `quiz.py`.

A missing or malformed file just disables the quiz; it never stops the timer. The quiz code lives in `quiz.py` and can be tried on its own: `python quiz.py --interval 20 --timeout 10`.

### Quiz stats and the Data report

Each question in `questions.json` also records its history:

```json
{"question": "Cuba", "answer": "Havana", "weight": 20, "asked": 7, "correct": 3, "wrong": 2, "last_asked": "2026-10-29T14:03:00"}
```

| Field | Meaning |
|---|---|
| `asked` | Times the question popped up |
| `correct` | Times answered correctly (close spellings count) |
| `wrong` | Times answered wrongly (submitting an empty box counts) |
| `last_asked` | Local date and time it last popped up |

Times it timed out without an answer = `asked − correct − wrong`. You don't need to add these fields: they start at 0 and are filled in automatically, so an existing `questions.json` keeps all its questions and weights.

When a question pops up, a line under it shows its weight and chance of being picked, how often it has been asked, when it was last asked, and how often it was answered right, wrong or not at all. After you answer, the line updates with the new counts.

**? → Data** opens a report window with:

- totals: questions, times asked, right, wrong, timed out, overall accuracy, questions never asked, and when the last question was asked
- a donut chart of right / wrong / timed-out answers (hover a slice for its count)
- the hardest and easiest questions, and those most likely to come up next
- a table of every question with its weight, chance, counts, accuracy and when it was last asked; click a heading to sort (again to reverse, a third time for file order) and type in **Filter** to search

**Refresh** reloads the numbers after you answer more questions. The report can also be opened on its own: `python report.py`.

### How answers are matched

Matching is done by `answer_check.py`. Each answer is marked **correct**, **close** or **wrong**:

1. **Normalisation.** Both your answer and the stored one are normalised first, so these never count against you: upper/lower case, leading, trailing or repeated spaces, accents (`Brasília` = `Brasilia`), punctuation and hyphens (`Porto Novo` = `Porto-Novo`), and `Saint` vs `St` (`Saint Johns` = `St. John's`).
2. **Exact match** after normalisation → correct.
3. **Spelling mistakes.** Otherwise typos are counted (a missing, extra, wrong or swapped letter is one typo each). Within the limit → close, which counts as correct for weighting.

   | Answer length (letters) | Typos allowed |
   |---|---|
   | 4 or fewer | 0 — must be exact (`Lome` is not close to `Lima`) |
   | 5–8 | 1 (`Otawa` is close to `Ottawa`) |
   | 9 or more | 2 |

   The limits are `EXACT_MAX_LETTERS`, `ONE_TYPO_MAX_LETTERS`, `ONE_TYPO` and `TWO_TYPOS` at the top of `answer_check.py`.
4. **Never close** if your answer is exactly the answer to a different question (`Kingstown` for Jamaica, whose answer is `Kingston`, is wrong), or if the answer contains digits (`365` is wrong, not close, for `366`).

### Alternative answers: `accepted_answers.json`

Some questions have more than one valid answer. `accepted_answers.json` (committed, next to `questions.json`) maps a question, written exactly as in the `"question"` field of `questions.json`, to a list of other answers to accept:

```json
{
  "Ukraine": ["Kiev"]
}
```

An alternative is matched with the same normalisation and typo rules as the main answer. The feedback still shows the main answer from `questions.json`. The file is optional: if it is missing, empty or malformed, the quiz works normally using only the main answers.

## Keyboard shortcuts

| Key | Action |
|---|---|
| `Space` | Start / Pause / Resume |
| `R` | Reset |
| `Escape` | Exit fullscreen |

## Generating call-graph diagrams

[code2flow](https://github.com/scottrogowski/code2flow) can produce a visual call-graph showing which functions call which. It requires **Graphviz** to render images.

### 1. Install Graphviz

| Platform | Command |
|---|---|
| **Linux — Debian / Ubuntu** | `sudo apt install graphviz` |
| **Linux — Fedora / RHEL** | `sudo dnf install graphviz` |
| **macOS** | `brew install graphviz` |
| **Windows** | `winget install graphviz` or download from [graphviz.org](https://graphviz.org/download/) |

### 2. Install code2flow

```bash
pip install code2flow
```

### 3. Generate diagrams

Full call graph of the whole file:

```bash
code2flow timer.py --output diagram.png
```

Drill into a specific function (`--downstream-depth` controls how many levels deep to follow):

```bash
code2flow timer.py --output diagram.png --target-function _time_up --downstream-depth 2
```

The `main()` function at the bottom of `timer.py` exists so the diagram has a clearly labelled root node. Without it, code2flow has no named entry point to anchor to.

## Requirements

- Python 3.10+
- `pygame>=2.5.0` — optional, for `.wav`/`.mp3` alarm files
