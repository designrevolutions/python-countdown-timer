# =============================================================================
#  QUIZ DATA REPORT
# =============================================================================
#
#  A window summarising the stats quiz.py records for every question: overall
#  totals, a chart of right / wrong / timed-out answers, the hardest and
#  easiest questions, and a sortable, filterable table of every question.
#
#  Opened by timer.py's "?" menu → Data.  Run it on its own to view the file:
#      python report.py
#      python report.py --questions my_questions.json
#
# =============================================================================

import argparse
import tkinter as tk
from tkinter import ttk

import quiz

# =============================================================================
#  SETTINGS
# =============================================================================

# Questions listed in each of the Hardest / Easiest / Most likely next cards
TOP_N = 5

# ── Colours ───────────────────────────────────────────────────────────────────
# Window and text colours come from quiz.py so the report matches the pop-up
CARD_BG         = "#26354a"
MUTED_COLOR     = "#9aa7b8"
TIMED_OUT_COLOR = "#8a94a6"
SELECTED_BG     = "#3d5578"

# Table columns: (key, heading, width, alignment)
COLUMNS = (
    ("question",   "Question",   220, "w"),
    ("answer",     "Answer",     170, "w"),
    ("weight",     "Weight",      70, "e"),
    ("chance",     "Chance",      70, "e"),
    ("asked",      "Asked",       60, "e"),
    ("correct",    "Right",       60, "e"),
    ("wrong",      "Wrong",       60, "e"),
    ("unanswered", "Timed out",   80, "e"),
    ("accuracy",   "Accuracy",    80, "e"),
    ("last_asked", "Last asked", 120, "w"),
)

# =============================================================================


def _pct(value: float | None, places: int = 0) -> str:
    return "—" if value is None else f"{value:.{places}%}"


def _fmt(key: str, value) -> str:
    """Text shown in a table cell for one raw row value."""
    if key == "weight":
        return f"{value:g}"
    if key == "chance":
        return _pct(value, 1)
    if key == "accuracy":
        return _pct(value)
    if key == "last_asked":
        return quiz.time_ago(value)
    return str(value)


def _rows(questions: list[dict]) -> list[dict]:
    """One flat record per question with every value the report shows."""
    return [
        {
            "question":   q["question"].strip(),
            "answer":     str(q["answer"]).strip(),
            "weight":     q["weight"],
            "chance":     quiz.chance(q, questions),
            "asked":      q["asked"],
            "correct":    q["correct"],
            "wrong":      q["wrong"],
            "unanswered": quiz.unanswered(q),
            "accuracy":   quiz.accuracy(q),
            # ISO timestamps sort chronologically as plain strings
            "last_asked": q.get("last_asked") if isinstance(q.get("last_asked"), str) else None,
        }
        for q in questions
    ]


class DataReport(tk.Toplevel):
    """Report window.  `get_questions` returns the current question list, so
    Refresh picks up answers given since the window was opened."""

    def __init__(self, parent: tk.Misc, get_questions, font_family: str = "Helvetica") -> None:
        super().__init__(parent, bg=quiz.POPUP_BG)
        self._get_questions = get_questions
        self._family = font_family
        self._sort_key: str | None = None  # None = file order
        self._sort_desc = False
        self._filter = tk.StringVar(self)
        self._filter.trace_add("write", lambda *_: self._fill_table())

        self.title("Quiz data")
        self.geometry("1100x780")
        self.minsize(760, 560)
        # A topmost main window (transparent mode) would otherwise cover this one
        self.attributes("-topmost", bool(parent.winfo_toplevel().attributes("-topmost")))
        self.bind("<Escape>", lambda _e: self.destroy())

        self._style()
        self._build_header()
        self._body = tk.Frame(self, bg=quiz.POPUP_BG)
        self._body.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))
        self.refresh()

    # ── Construction ──────────────────────────────────────────────────────────

    def _font(self, size: int, *style: str) -> tuple:
        return (self._family, size, *style)

    def _style(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")  # the native Windows theme ignores custom colours
        style.configure(
            "Report.Treeview", background=CARD_BG, fieldbackground=CARD_BG,
            foreground=quiz.TEXT_COLOR, rowheight=26, borderwidth=0, font=self._font(11),
        )
        style.map("Report.Treeview", background=[("selected", SELECTED_BG)])
        style.configure(
            "Report.Treeview.Heading", background=quiz.POPUP_BG, foreground=quiz.ACCENT_COLOR,
            font=self._font(11, "bold"), relief="flat", borderwidth=0,
        )
        style.map("Report.Treeview.Heading", background=[("active", SELECTED_BG)])

    def _button(self, parent: tk.Misc, text: str, command) -> tk.Button:
        return tk.Button(
            parent, text=text, command=command, font=self._font(12),
            bg="#2d2d2d", fg="#eeeeee", activebackground="#505050", activeforeground="#ffffff",
            relief=tk.FLAT, padx=16, pady=5, cursor="hand2", bd=0,
        )

    def _build_header(self) -> None:
        header = tk.Frame(self, bg=quiz.POPUP_BG)
        header.pack(fill=tk.X, padx=20, pady=(16, 12))
        tk.Label(header, text="Quiz data", font=self._font(22, "bold"),
                 fg=quiz.ACCENT_COLOR, bg=quiz.POPUP_BG).pack(side=tk.LEFT)
        self._button(header, "Close", self.destroy).pack(side=tk.RIGHT, padx=(8, 0))
        self._button(header, "Refresh", self.refresh).pack(side=tk.RIGHT)

    def _card(self, parent: tk.Misc, title: str | None = None) -> tk.Frame:
        card = tk.Frame(parent, bg=CARD_BG, padx=14, pady=10)
        if title:
            tk.Label(card, text=title, font=self._font(13, "bold"),
                     fg=quiz.TEXT_COLOR, bg=CARD_BG, anchor="w").pack(fill=tk.X, pady=(0, 6))
        return card

    def refresh(self) -> None:
        """Rebuild every section from the current questions."""
        for child in self._body.winfo_children():
            child.destroy()
        self._data = _rows(self._get_questions())
        if not self._data:
            tk.Label(self._body, text="No quiz questions loaded.\nCheck the questions file.",
                     font=self._font(16), fg=MUTED_COLOR, bg=quiz.POPUP_BG).pack(expand=True)
            return
        self._build_tiles()
        self._build_charts()
        self._build_table()

    # ── Headline numbers ──────────────────────────────────────────────────────

    def _build_tiles(self) -> None:
        rows = self._data
        asked   = sum(r["asked"] for r in rows)
        correct = sum(r["correct"] for r in rows)
        wrong   = sum(r["wrong"] for r in rows)
        stamps  = [r["last_asked"] for r in rows if r["last_asked"]]
        tiles = (
            ("Questions",   len(rows)),
            ("Times asked", asked),
            ("Right",       correct),
            ("Wrong",       wrong),
            ("Timed out",   sum(r["unanswered"] for r in rows)),
            ("Accuracy",    _pct(correct / (correct + wrong) if correct + wrong else None)),
            ("Never asked", sum(1 for r in rows if not r["asked"])),
            ("Last quiz",   quiz.time_ago(max(stamps)) if stamps else "never"),
        )
        row = tk.Frame(self._body, bg=quiz.POPUP_BG)
        row.pack(fill=tk.X, pady=(0, 12))
        for i, (label, value) in enumerate(tiles):
            row.columnconfigure(i, weight=1, uniform="tile")
            tile = self._card(row)
            tile.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 8, 0))
            # Text values such as "3 hours ago" need a smaller font to fit the tile
            size = 18 if isinstance(value, int) or len(value) <= 5 else 13
            tk.Label(tile, text=str(value), font=self._font(size, "bold"),
                     fg=quiz.TEXT_COLOR, bg=CARD_BG).pack()
            tk.Label(tile, text=label, font=self._font(10), fg=MUTED_COLOR, bg=CARD_BG).pack()

    # ── Pie chart and ranked lists ────────────────────────────────────────────

    def _build_charts(self) -> None:
        rows = self._data
        row = tk.Frame(self._body, bg=quiz.POPUP_BG)
        row.pack(fill=tk.X, pady=(0, 12))

        pie = self._card(row, "All answers")
        pie.pack(side=tk.LEFT, fill=tk.Y)
        self._draw_pie(pie, (
            ("Right",     sum(r["correct"] for r in rows),    quiz.CORRECT_COLOR),
            ("Wrong",     sum(r["wrong"] for r in rows),      quiz.WRONG_COLOR),
            ("Timed out", sum(r["unanswered"] for r in rows), TIMED_OUT_COLOR),
        ))

        def score(r: dict) -> str:
            return f"{_pct(r['accuracy'])}  ({r['correct']}/{r['correct'] + r['wrong']})"

        # Hardest needs at least one miss and easiest one correct answer, so a
        # small history doesn't list the same perfect question in both
        hardest = sorted((r for r in rows if r["wrong"]), key=lambda r: (r["accuracy"], -r["wrong"]))
        easiest = sorted((r for r in rows if r["correct"]), key=lambda r: (-r["accuracy"], -r["correct"]))
        likely  = sorted(rows, key=lambda r: -r["weight"])
        lists = (
            ("Hardest",          hardest, score, "No wrong answers yet"),
            ("Easiest",          easiest, score, "No right answers yet"),
            ("Most likely next", likely,  lambda r: _pct(r["chance"], 1), ""),
        )
        for title, ranked, value, empty in lists:
            card = self._card(row, title)
            card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(8, 0))
            if not ranked:
                tk.Label(card, text=empty, font=self._font(11), fg=MUTED_COLOR,
                         bg=CARD_BG, anchor="w").pack(fill=tk.X)
            for i, r in enumerate(ranked[:TOP_N], 1):
                line = tk.Frame(card, bg=CARD_BG)
                line.pack(fill=tk.X, pady=1)
                # Value packed first so a long question is the one that gets clipped
                tk.Label(line, text=value(r), font=self._font(11),
                         fg=MUTED_COLOR, bg=CARD_BG).pack(side=tk.RIGHT, padx=(10, 0))
                tk.Label(line, text=f"{i}. {r['question']}", font=self._font(11),
                         fg=quiz.TEXT_COLOR, bg=CARD_BG, anchor="w").pack(side=tk.LEFT)

    def _draw_pie(self, parent: tk.Misc, parts: tuple) -> None:
        """Donut chart of (label, count, colour) parts with a legend.  Hovering
        a slice shows its count in the middle; otherwise the middle shows accuracy."""
        size, pad = 200, 4
        hole = size * 0.22  # inset of the hole from the edge
        total = sum(n for _, n, _ in parts)
        canvas = tk.Canvas(parent, width=size, height=size, bg=CARD_BG, highlightthickness=0)
        canvas.pack(side=tk.LEFT)
        box = (pad, pad, size - pad, size - pad)

        if not total:
            canvas.create_oval(*box, outline=MUTED_COLOR, width=2)
        start = 90.0  # first slice starts at 12 o'clock and runs clockwise
        for label, n, colour in parts:
            if not n:
                continue
            tag = f"slice{start}"
            if n == total:
                # A 360° arc draws nothing in Tk, so a lone slice is a circle
                canvas.create_oval(*box, fill=colour, outline=CARD_BG, width=2, tags=tag)
            else:
                extent = -360 * n / total
                # The CARD_BG outline leaves a thin gap between slices
                canvas.create_arc(*box, start=start, extent=extent, fill=colour,
                                  outline=CARD_BG, width=2, style=tk.PIESLICE, tags=tag)
                start += extent
            canvas.tag_bind(tag, "<Enter>", lambda _e, t=f"{n}", c=f"{label} · {n / total:.0%}": show(t, c))
            canvas.tag_bind(tag, "<Leave>", lambda _e: show(*default))
        canvas.create_oval(hole, hole, size - hole, size - hole, fill=CARD_BG, outline=CARD_BG)

        right, wrong = parts[0][1], parts[1][1]
        default = (_pct(right / (right + wrong) if right + wrong else None), "accuracy")
        value = canvas.create_text(size / 2, size / 2 - 8, font=self._font(20, "bold"), fill=quiz.TEXT_COLOR)
        caption = canvas.create_text(size / 2, size / 2 + 16, font=self._font(10), fill=MUTED_COLOR)

        def show(text: str, sub: str) -> None:
            canvas.itemconfigure(value, text=text)
            canvas.itemconfigure(caption, text=sub)
        show(*default)

        legend = tk.Frame(parent, bg=CARD_BG)
        legend.pack(side=tk.LEFT, padx=(14, 0))
        for label, n, colour in parts:
            line = tk.Frame(legend, bg=CARD_BG)
            line.pack(anchor="w", pady=3)
            swatch = tk.Canvas(line, width=12, height=12, bg=CARD_BG, highlightthickness=0)
            swatch.create_rectangle(0, 0, 12, 12, fill=colour, outline="")
            swatch.pack(side=tk.LEFT, padx=(0, 6))
            tk.Label(line, text=label, font=self._font(11), fg=quiz.TEXT_COLOR, bg=CARD_BG).pack(side=tk.LEFT)
            tk.Label(line, text=f"{n}  ({_pct(n / total if total else None)})", font=self._font(11),
                     fg=MUTED_COLOR, bg=CARD_BG).pack(side=tk.LEFT, padx=(8, 0))

    # ── Table of every question ───────────────────────────────────────────────

    def _build_table(self) -> None:
        card = self._card(self._body)
        card.pack(fill=tk.BOTH, expand=True)

        top = tk.Frame(card, bg=CARD_BG)
        top.pack(fill=tk.X, pady=(0, 8))
        tk.Label(top, text=f"All questions ({len(self._data)})", font=self._font(13, "bold"),
                 fg=quiz.TEXT_COLOR, bg=CARD_BG).pack(side=tk.LEFT)
        tk.Label(top, text="Click a heading to sort", font=self._font(10),
                 fg=MUTED_COLOR, bg=CARD_BG).pack(side=tk.LEFT, padx=12)
        tk.Entry(
            top, textvariable=self._filter, width=24, font=self._font(11),
            bg="#2d2d2d", fg="#eeeeee", insertbackground="#eeeeee", relief=tk.FLAT,
        ).pack(side=tk.RIGHT, ipady=4)
        tk.Label(top, text="Filter:", font=self._font(11), fg=MUTED_COLOR, bg=CARD_BG).pack(side=tk.RIGHT, padx=6)

        frame = tk.Frame(card, bg=CARD_BG)
        frame.pack(fill=tk.BOTH, expand=True)
        self._tree = ttk.Treeview(frame, columns=[c[0] for c in COLUMNS], show="headings",
                                  style="Report.Treeview")
        for key, _title, width, anchor in COLUMNS:
            self._tree.heading(key, command=lambda k=key: self._sort_by(k), anchor=anchor)
            self._tree.column(key, width=width, minwidth=50, anchor=anchor,
                              stretch=key in ("question", "answer"))
        self._tree.tag_configure("never", foreground=MUTED_COLOR)
        scroll = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=self._tree.yview)
        self._tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self._tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._fill_table()

    def _sort_by(self, key: str) -> None:
        """First click sorts by the column, the second reverses it, the third
        goes back to file order."""
        # Numbers read best largest-first; text A–Z
        first_desc = key not in ("question", "answer")
        if self._sort_key != key:
            self._sort_key, self._sort_desc = key, first_desc
        elif self._sort_desc == first_desc:
            self._sort_desc = not first_desc
        else:
            self._sort_key = None
        self._fill_table()

    def _fill_table(self) -> None:
        if not getattr(self, "_tree", None) or not self._tree.winfo_exists():
            return
        self._tree.delete(*self._tree.get_children())

        needle = self._filter.get().strip().casefold()
        rows = [r for r in self._data
                if needle in r["question"].casefold() or needle in r["answer"].casefold()]
        key = self._sort_key
        if key:
            # Blank values (never answered / never asked) always go last
            blank = [r for r in rows if r[key] is None]
            rows = sorted((r for r in rows if r[key] is not None),
                          key=lambda r: r[key].casefold() if isinstance(r[key], str) else r[key],
                          reverse=self._sort_desc) + blank

        for col, title, _w, _a in COLUMNS:
            arrow = (" ▼" if self._sort_desc else " ▲") if col == key else ""
            self._tree.heading(col, text=title + arrow)
        for r in rows:
            self._tree.insert("", tk.END, values=[_fmt(c[0], r[c[0]]) for c in COLUMNS],
                              tags=() if r["asked"] else ("never",))


# =============================================================================
#  Standalone viewer
# =============================================================================


def main() -> None:
    p = argparse.ArgumentParser(description="Quiz data report.")
    p.add_argument("--questions", default=quiz.QUESTIONS_FILE, metavar="FILE")
    args = p.parse_args()

    root = tk.Tk()
    root.withdraw()  # only the report window is shown
    report = DataReport(root, lambda: quiz.load_questions(args.questions)[1])
    root.wait_window(report)
    root.destroy()


if __name__ == "__main__":
    main()
