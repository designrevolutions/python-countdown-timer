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
#        {"question": "What is the capital of France?", "answer": "Paris"},
#        {"question": "What is the capital of Japan?",  "answer": "Tokyo"}
#      ]
#
#  Answers are compared case-insensitively, ignoring leading/trailing spaces.
#
# =============================================================================

import argparse
import json
import os
import random
import sys
import tkinter as tk

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

# ── Colours ───────────────────────────────────────────────────────────────────
# Deliberately not pure black: timer.py's transparent mode turns every
# BACKGROUND_COLOR pixel (default "#000000") see-through.
POPUP_BG      = "#1e2a3a"
ACCENT_COLOR  = "#ffcc00"
TEXT_COLOR    = "#ffffff"
CORRECT_COLOR = "#44dd66"
WRONG_COLOR   = "#ff6b6b"

# =============================================================================


def _resolve(path: str) -> str:
    """Resolve a relative path against this file's folder (absolute paths pass through)."""
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), path)


def _warn(message: str) -> None:
    # Under pythonw sys.stderr is None; print() then quietly does nothing
    print(f"[quiz] {message}", file=sys.stderr)


def load_questions(path: str = QUESTIONS_FILE) -> list[dict[str, str]]:
    """Read the questions file once.  Never raises: a missing or malformed file
    gives an empty list, and individual bad entries are skipped."""
    path = _resolve(path)
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        _warn(f"questions file not found: {path}")
        return []
    except (OSError, ValueError) as exc:  # ValueError covers JSON and decoding errors
        _warn(f"could not read {path}: {exc}")
        return []

    if not isinstance(data, list):
        _warn(f"{path} should contain a list of question objects")
        return []

    questions = []
    for item in data:
        if not isinstance(item, dict):
            continue
        q, a = item.get("question"), item.get("answer")
        # Allow numeric answers in the JSON (e.g. "answer": 7)
        if isinstance(q, str) and isinstance(a, (str, int, float)) and q.strip() and str(a).strip():
            questions.append({"question": q.strip(), "answer": str(a).strip()})

    skipped = len(data) - len(questions)
    if skipped:
        _warn(f"skipped {skipped} malformed entr{'y' if skipped == 1 else 'ies'} in {path}")
    return questions


def _normalise(text: str) -> str:
    return text.strip().casefold()


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
        self._questions  = load_questions(questions_file)  # loaded once, up front
        self._current: dict[str, str] | None = None        # question being asked

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

        # Avoid asking the same question twice in a row when there's a choice
        choices = [q for q in self._questions if q is not self._current] or self._questions
        self._current = random.choice(choices)

        self._question.configure(text=self._current["question"])
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

        if _normalise(given) == _normalise(self._current["answer"]):
            self._result.configure(text="Well done!")
            self._flash(lambda on: self._result.configure(fg=CORRECT_COLOR if on else POPUP_BG))
        else:
            self._result.configure(
                text=f"Not quite. The answer is: {self._current['answer']}", fg=WRONG_COLOR,
            )
        self._result.pack()
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
