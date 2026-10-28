# =============================================================================
#  QUIZ POP-UP
# =============================================================================
#
#  Shows a random question from a JSON file inside an existing tkinter window,
#  once per INTERVAL_SECONDS window at a random moment within that window.
#
#  Used by timer.py, but has no dependency on it.  Run it on its own to try it:
#      python quiz.py
#      python quiz.py --interval 20 --timeout 10 --questions my_questions.json
#
#  Questions file format — a flat list of objects:
#      [
#        {"question": "What is the capital of France?", "answer": "Paris", "weight": 20},
#        {"question": "What is the capital of Japan?",  "answer": "Tokyo", "weight": 20}
#      ]
#
#  Answers are checked by answer_check.py, which ignores case, accents and
#  punctuation, accepts alternatives from accepted_answers.json, and treats
#  small spelling mistakes as "close" (counted as correct for weighting).
#
#  "weight" sets how likely a question is to be picked: one with weight 40 is
#  twice as likely as one with weight 20.  Every question starts at DEFAULT_WEIGHT.
#    Wrong answer   → weight rises by WEIGHT_UP (no upper limit).
#    Correct answer → weight drops to DEFAULT_WEIGHT if above it, then falls by
#                     WEIGHT_DOWN, never below MIN_WEIGHT.  With the defaults:
#                     20 → 15 → 10 → 5 → 1 → 1 ...
#    No answer      → unchanged.
#  Weights are saved back to the file so they survive restarts.  "weight" may
#  be omitted when adding questions; it then starts at DEFAULT_WEIGHT.
#
# =============================================================================

import argparse
import json
import os
import random
import sys
import tkinter as tk

from answer_check import CLOSE, CORRECT, check_answer, load_accepted

# =============================================================================
#  SETTINGS  —  defaults; callers can override each one via QuizPopup(...)
# =============================================================================

# Length (seconds) of each quiz window; one question pops up at a random
# moment inside every window
INTERVAL_SECONDS = 5 * 60

# Seconds the user has to answer before the pop-up is dismissed automatically
TIMEOUT_SECONDS = 30

# Seconds the "Well done!" / correct-answer message stays on screen
FEEDBACK_SECONDS = 4

# Questions file; relative paths are resolved from this file's folder, so it
# works no matter which directory the program is launched from
QUESTIONS_FILE = "questions.json"

# ── Weighting ─────────────────────────────────────────────────────────────────

# Weight every question starts at; leaves room below for correct answers to
# make a question progressively less likely
DEFAULT_WEIGHT = 20

# Floor for the weight.  Must stay above 0: a question at 0 would never be
# asked again, and random.choices() fails if every weight is 0
MIN_WEIGHT = 1

# Amount added to a question's weight on every wrong answer (no upper limit)
WEIGHT_UP = 5

# Amount subtracted on every correct answer (after capping at DEFAULT_WEIGHT)
WEIGHT_DOWN = 5

# ── Colours ───────────────────────────────────────────────────────────────────
# Deliberately not pure black: timer.py's transparent mode turns every
# BACKGROUND_COLOR pixel (default "#000000") see-through.
POPUP_BG      = "#1e2a3a"
ACCENT_COLOR  = "#ffcc00"
TEXT_COLOR    = "#ffffff"
CORRECT_COLOR = "#44dd66"
CLOSE_COLOR   = "#66ccff"  # right answer, misspelt
WRONG_COLOR   = "#ff6b6b"

# =============================================================================


def _resolve(path: str) -> str:
    """Resolve a relative path against this file's folder (absolute paths pass through)."""
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), path)


def _warn(message: str) -> None:
    # Under pythonw sys.stderr is None; print() then quietly does nothing
    print(f"[quiz] {message}", file=sys.stderr)


def load_questions(path: str = QUESTIONS_FILE) -> tuple[list, list[dict]]:
    """Read the questions file once.  Never raises: a missing or malformed file
    gives empty lists, and individual bad entries are skipped.

    Returns (all_entries, questions).  `questions` holds the valid entries — the
    very same dict objects as in `all_entries`, so updating a weight on one is
    reflected in what save_questions() writes, and malformed entries are kept
    in the file untouched rather than silently deleted."""
    path = _resolve(path)
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        _warn(f"questions file not found: {path} (copy questions.sample.json to create it)")
        return [], []
    except (OSError, ValueError) as exc:  # ValueError covers JSON and decoding errors
        _warn(f"could not read {path}: {exc}")
        return [], []

    if not isinstance(data, list):
        _warn(f"{path} should contain a list of question objects")
        return [], []

    questions = []
    for item in data:
        if not isinstance(item, dict):
            continue
        q, a = item.get("question"), item.get("answer")
        # Allow numeric answers in the JSON (e.g. "answer": 7)
        if isinstance(q, str) and isinstance(a, (str, int, float)) and q.strip() and str(a).strip():
            # Missing or unusable weight (bool, text, zero, negative) → default;
            # a small positive one (e.g. 0.5) is raised to the floor.
            # bool is excluded because it is a subclass of int in Python.
            m = item.get("weight")
            if isinstance(m, bool) or not isinstance(m, (int, float)) or m <= 0:
                item["weight"] = DEFAULT_WEIGHT
            elif m < MIN_WEIGHT:
                item["weight"] = MIN_WEIGHT
            questions.append(item)

    skipped = len(data) - len(questions)
    if skipped:
        _warn(f"skipped {skipped} malformed entr{'y' if skipped == 1 else 'ies'} in {path}")
    return data, questions


def save_questions(path: str, entries: list) -> None:
    """Write entries back to the questions file, one question per line so it
    stays easy to edit by hand.  Never raises; a failed save only loses the
    latest weight change."""
    path = _resolve(path)
    body = ",\n".join("  " + json.dumps(item, ensure_ascii=False) for item in entries)
    text = f"[\n{body}\n]\n" if entries else "[]\n"
    # Write to a temp file and swap it in, so a crash mid-write can't leave
    # a half-written (and therefore unreadable) questions file behind
    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, path)
    except OSError as exc:
        _warn(f"could not save weights to {path}: {exc}")


class QuizPopup:
    """Quiz panel drawn inside `parent` (any tkinter widget) with place()."""

    # ms between flash toggles
    _FLASH_MS = 250

    # Number of toggles for the attention flash when a question first appears
    _ATTENTION_TOGGLES = 12

    def __init__(
        self,
        parent: tk.Misc,
        questions_file: str = QUESTIONS_FILE,
        interval_s: float = INTERVAL_SECONDS,
        timeout_s: float = TIMEOUT_SECONDS,
        feedback_s: float = FEEDBACK_SECONDS,
        font_family: str = "Helvetica",
        font_size: int = 18,
    ) -> None:
        self._parent     = parent
        self.interval_s  = interval_s
        self.timeout_s   = timeout_s
        self.feedback_s  = feedback_s
        self._questions_file = questions_file
        # Loaded once, up front; only rewritten when a weight changes
        self._entries, self._questions = load_questions(questions_file)
        self._accepted = load_accepted()  # question → alternative answers
        self._current: dict | None = None  # question being asked

        # tkinter after() handle IDs — None means not currently scheduled
        self._window_id:   str | None = None  # start of the next quiz window
        self._trigger_id:  str | None = None  # random pop-up moment in this window
        self._timeout_id:  str | None = None  # auto-dismiss if unanswered
        self._feedback_id: str | None = None  # dismiss after showing the result
        self._flash_id:    str | None = None

        self._build(font_family, font_size)

    # ── UI construction ───────────────────────────────────────────────────────

    def _build(self, family: str, size: int) -> None:
        self._frame = tk.Frame(
            self._parent, bg=POPUP_BG, padx=24, pady=18,
            highlightthickness=8, highlightbackground=ACCENT_COLOR, highlightcolor=ACCENT_COLOR,
        )
        self._title = tk.Label(
            self._frame, text="Quiz time!", font=(family, size + 8, "bold"),
            fg=ACCENT_COLOR, bg=POPUP_BG,
        )
        self._question = tk.Label(
            self._frame, font=(family, size), fg=TEXT_COLOR, bg=POPUP_BG, justify="center",
        )
        self._title.pack(pady=(0, 10))
        self._question.pack(pady=(0, 14))

        # Entry + Submit, hidden once an answer is given
        self._answer_row = tk.Frame(self._frame, bg=POPUP_BG)
        self._entry = tk.Entry(
            self._answer_row, width=20, justify="center", font=(family, size),
            bg="#2d2d2d", fg="#eeeeee", insertbackground="#eeeeee", relief=tk.FLAT,
        )
        self._entry.pack(side=tk.LEFT, padx=6, ipady=6)
        # A borderless (overrideredirect) window never takes keyboard focus on its
        # own, so grab it explicitly when the box is clicked
        self._entry.bind("<Button-1>", lambda _e: self._entry.focus_force())
        self._entry.bind("<Return>",   lambda _e: self._submit_answer())

        tk.Button(
            self._answer_row, text="Submit", command=self._submit_answer,
            font=(family, size - 4), bg="#2d2d2d", fg="#eeeeee",
            activebackground="#505050", activeforeground="#ffffff",
            relief=tk.FLAT, padx=16, pady=6, cursor="hand2", bd=0,
        ).pack(side=tk.LEFT, padx=6)

        self._result = tk.Label(self._frame, font=(family, size + 4, "bold"), bg=POPUP_BG)

        # Keep long questions wrapped to the panel width
        self._frame.bind("<Configure>", self._on_resize)

    def _on_resize(self, event: tk.Event) -> None:
        wrap = max(100, event.width - 60)
        self._question.configure(wraplength=wrap)
        self._result.configure(wraplength=wrap)

    # ── Public API ────────────────────────────────────────────────────────────

    def start(self) -> None:
        """Begin the automatic schedule: one question per interval, indefinitely."""
        self._start_window()

    def stop(self) -> None:
        """Cancel the schedule and hide any visible question."""
        self._cancel("_window_id", "_trigger_id")
        self._hide()

    def show_now(self) -> None:
        """Show a question immediately (replacing any visible one) and restart
        the schedule so the next automatic question is timed from now."""
        self._show()
        # This question occupies the start of the fresh window, so the
        # automatic one must land after it has finished
        self._start_window(earliest=self._busy_s)

    # ── Scheduling ────────────────────────────────────────────────────────────

    @property
    def _busy_s(self) -> float:
        """Longest time one question can stay on screen."""
        return self.timeout_s + self.feedback_s

    def _start_window(self, earliest: float = 0.0) -> None:
        """Open a new quiz window and pick a random moment inside it.  The
        moment is capped so the pop-up always closes before the window ends,
        meaning consecutive questions can never overlap."""
        self._cancel("_window_id", "_trigger_id")
        if not self._questions:
            return
        latest   = max(0.0, self.interval_s - self._busy_s)
        earliest = min(earliest, latest)
        delay    = random.uniform(earliest, latest)
        self._trigger_id = self._frame.after(int(delay * 1000), self._show)
        self._window_id  = self._frame.after(int(self.interval_s * 1000), self._start_window)

    def _cancel(self, *names: str) -> None:
        """Cancel the named after() handles, e.g. _cancel("_timeout_id")."""
        for name in names:
            handle = getattr(self, name)
            if handle is not None:
                self._frame.after_cancel(handle)
                setattr(self, name, None)

    # ── Show / answer / hide ──────────────────────────────────────────────────

    def _show(self) -> None:
        self._trigger_id = None
        self._cancel("_timeout_id", "_feedback_id", "_flash_id")
        self._result.pack_forget()

        if not self._questions:
            # Only reachable via show_now(); explain instead of failing silently
            self._current = None
            self._question.configure(text="No quiz questions loaded.\nCheck the questions file.")
            self._answer_row.pack_forget()
            self._place()
            self._feedback_id = self._frame.after(int(self.feedback_s * 1000), self._hide)
            return

        # Avoid asking the same question twice in a row when there's a choice,
        # then pick with probability proportional to each question's weight
        choices = [q for q in self._questions if q is not self._current] or self._questions
        self._current = random.choices(choices, weights=[q["weight"] for q in choices])[0]

        self._question.configure(text=self._current["question"].strip())
        self._entry.delete(0, tk.END)
        self._answer_row.pack()
        self._place()
        self._entry.focus_set()

        self._flash(self._attention, self._ATTENTION_TOGGLES)
        self._timeout_id = self._frame.after(int(self.timeout_s * 1000), self._hide)

    def _place(self) -> None:
        self._frame.place(relx=0.5, rely=0.5, anchor="center", relwidth=0.8)
        self._frame.lift()

    def _submit_answer(self) -> None:
        given = self._entry.get()
        if self._current is None or not given.strip():
            return
        self._cancel("_timeout_id", "_flash_id")
        self._attention(True)  # in case the attention flash was mid-cycle
        self._release_focus()
        self._answer_row.pack_forget()

        answer = str(self._current["answer"]).strip()
        others = [q["answer"] for q in self._questions if q is not self._current]
        accepted = self._accepted.get(self._current["question"].strip())
        verdict = check_answer(given, answer, others, accepted)
        if verdict in (CORRECT, CLOSE):
            # A question that had been missed is first brought back to the
            # default, so one correct answer treats it like any other question
            # answered correctly once; repeated correct answers keep lowering it
            weight = min(self._current["weight"], DEFAULT_WEIGHT) - WEIGHT_DOWN
            self._current["weight"] = max(MIN_WEIGHT, weight)
            if verdict == CORRECT:
                self._result.configure(text="Well done!")
                self._flash(lambda on: self._result.configure(fg=CORRECT_COLOR if on else POPUP_BG))
            else:
                self._result.configure(text=f"Correct, but check the spelling: {answer}", fg=CLOSE_COLOR)
        else:
            # Grows on every wrong answer, so repeatedly missed questions keep
            # coming up more often until they are answered correctly
            self._current["weight"] += WEIGHT_UP
            self._result.configure(text=f"Not quite. The answer is: {answer}", fg=WRONG_COLOR)
        self._result.pack()
        save_questions(self._questions_file, self._entries)
        self._feedback_id = self._frame.after(int(self.feedback_s * 1000), self._hide)

    def _hide(self) -> None:
        self._cancel("_timeout_id", "_feedback_id", "_flash_id")
        self._release_focus()
        self._attention(True)
        self._frame.place_forget()

    def _release_focus(self) -> None:
        """Hand keyboard focus back to the window so its shortcuts work again."""
        if self._frame.focus_get() is self._entry:
            self._frame.winfo_toplevel().focus_set()

    # ── Flash animation ───────────────────────────────────────────────────────

    def _attention(self, on: bool) -> None:
        colour = ACCENT_COLOR if on else POPUP_BG
        self._frame.configure(highlightbackground=colour, highlightcolor=colour)
        self._title.configure(fg=colour)

    def _flash(self, apply, toggles: int | None = None, on: bool = True) -> None:
        """Call apply(on) with alternating True/False every _FLASH_MS.  Stops
        (ending on True) after `toggles` calls, or runs until cancelled if None."""
        apply(on)
        if toggles is not None:
            toggles -= 1
            if toggles <= 0:
                apply(True)
                self._flash_id = None
                return
        self._flash_id = self._frame.after(self._FLASH_MS, self._flash, apply, toggles, not on)


# =============================================================================
#  Standalone demo
# =============================================================================


def main() -> None:
    p = argparse.ArgumentParser(description="Quiz pop-up demo.")
    p.add_argument("--interval",  type=float, default=INTERVAL_SECONDS, metavar="SECS")
    p.add_argument("--timeout",   type=float, default=TIMEOUT_SECONDS,  metavar="SECS")
    p.add_argument("--questions", default=QUESTIONS_FILE, metavar="FILE")
    args = p.parse_args()

    root = tk.Tk()
    root.title("Quiz")
    root.geometry("700x450")
    root.configure(bg="#000000")

    quiz = QuizPopup(root, args.questions, args.interval, args.timeout)
    tk.Button(root, text="?", command=quiz.show_now).pack(side=tk.BOTTOM, pady=10)
    quiz.start()
    root.mainloop()


if __name__ == "__main__":
    main()
