# =============================================================================
#  ANSWER CHECK
# =============================================================================
#
#  Decides whether a typed quiz answer is right, nearly right, or wrong.
#  Used by quiz.py, but has no dependency on it or on tkinter.
#
#      check_answer(given, answer, other_answers, accepted=None)
#          → "correct" | "close" | "wrong"
#
#  1. Normalisation.  Both sides are normalised first, so these differences
#     never matter: case, leading/trailing and repeated spaces, accents
#     (é → e), punctuation and hyphens, and "Saint" vs "St".
#     So "st johns", "Saint John's" and "St. John's" are all the same answer.
#
#  2. Exact match.  A normalised guess equal to the answer, or to any accepted
#     alternative, is "correct".
#
#  3. Typos.  Otherwise the typos are counted with Damerau-Levenshtein
#     distance (a missing, extra, wrong or swapped letter is one typo each).
#     The number allowed depends on the length of the answer being compared
#     against (letters and digits, not counting spaces); see the settings
#     below.  Within the limit → "close".  The same rule applies to accepted
#     alternatives.
#
#  4. Never "close" when:
#       - the guess exactly matches the answer to a different question
#         (e.g. "Kingstown" for Jamaica, whose answer is "Kingston"), or
#       - the answer contains digits ("365" is not close to "366").
#
#  Accepted alternatives come from ACCEPTED_ANSWERS_FILE, a JSON object that
#  maps a question (exactly as written in the questions file) to a list of
#  other valid answers:
#      {
#        "Ukraine": ["Kiev"]
#      }
#  The file is optional; if it is missing, empty or malformed the quiz just
#  uses the main answers.
#
# =============================================================================

import json
import os
import re
import sys
import unicodedata

# =============================================================================
#  SETTINGS
# =============================================================================

# Answers up to this many letters must be typed exactly (after normalisation)
EXACT_MAX_LETTERS = 4

# Answers up to this many letters allow ONE_TYPO; longer ones allow TWO_TYPOS
ONE_TYPO_MAX_LETTERS = 8

ONE_TYPO  = 1
TWO_TYPOS = 2

# Alternative answers file; relative paths are resolved from this file's folder
ACCEPTED_ANSWERS_FILE = "accepted_answers.json"

# =============================================================================

CORRECT = "correct"
CLOSE   = "close"
WRONG   = "wrong"


def _warn(message: str) -> None:
    # Under pythonw sys.stderr is None; print() then quietly does nothing
    print(f"[answer_check] {message}", file=sys.stderr)


def normalise(text) -> str:
    """Lower-case, accent-free, punctuation-free form of `text` with single
    spaces, and "saint" shortened to "st"."""
    text = unicodedata.normalize("NFKD", str(text))
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).casefold()
    # Apostrophes join their word ("John's" → "johns"); any other punctuation,
    # hyphens included, separates words ("Porto-Novo" → "porto novo")
    text = re.sub(r"['‘’`]", "", text)
    text = re.sub(r"[\W_]+", " ", text)
    words = ["st" if w == "saint" else w for w in text.split()]
    return " ".join(words)


def allowed_typos(answer: str) -> int:
    """Typos allowed for a normalised answer, based on its length."""
    letters = len(answer.replace(" ", ""))
    if letters <= EXACT_MAX_LETTERS:
        return 0
    if letters <= ONE_TYPO_MAX_LETTERS:
        return ONE_TYPO
    return TWO_TYPOS


def typo_count(a: str, b: str) -> int:
    """Damerau-Levenshtein distance (optimal string alignment): the number of
    missing, extra, wrong or swapped-adjacent characters between a and b."""
    prev2: list[int] = []
    prev = list(range(len(b) + 1))
    for i in range(1, len(a) + 1):
        cur = [i] + [0] * len(b)
        for j in range(1, len(b) + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost)
            if i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                cur[j] = min(cur[j], prev2[j - 2] + 1)
        prev2, prev = prev, cur
    return prev[-1]


def check_answer(given, answer, other_answers, accepted=None) -> str:
    """Return "correct", "close" or "wrong" for `given` against `answer` and
    its `accepted` alternatives.  `other_answers` are the answers to the other
    questions; a guess equal to one of them is never treated as a typo."""
    guess = normalise(given)
    if not guess:
        return WRONG
    candidates = [c for c in (normalise(a) for a in [answer, *(accepted or [])]) if c]

    if guess in candidates:
        return CORRECT

    if guess in {normalise(a) for a in other_answers}:
        return WRONG

    for candidate in candidates:
        if any(ch.isdigit() for ch in candidate):
            continue
        limit = allowed_typos(candidate)
        if limit and typo_count(guess, candidate) <= limit:
            return CLOSE
    return WRONG


def load_accepted(path: str = ACCEPTED_ANSWERS_FILE) -> dict[str, list[str]]:
    """Read the accepted-alternatives file.  Never raises: a missing, empty or
    malformed file gives {}, and individual bad entries are skipped."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), path)
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except FileNotFoundError:
        return {}
    except OSError as exc:
        _warn(f"could not read {path}: {exc}")
        return {}
    if not text.strip():
        return {}
    try:
        data = json.loads(text)
    except ValueError as exc:
        _warn(f"could not read {path}: {exc}")
        return {}
    if not isinstance(data, dict):
        _warn(f"{path} should contain an object mapping questions to lists of answers")
        return {}

    accepted = {}
    for question, answers in data.items():
        if isinstance(answers, (str, int, float)) and not isinstance(answers, bool):
            answers = [answers]  # tolerate a single answer written without a list
        if not isinstance(answers, list):
            continue
        valid = [str(a) for a in answers
                 if isinstance(a, (str, int, float)) and not isinstance(a, bool) and str(a).strip()]
        if valid:
            accepted[question.strip()] = valid
    return accepted
