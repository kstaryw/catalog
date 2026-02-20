# -----------------------------------------------
#  6. Word Frequency Analysis:
# 
#  Objective: Perform a word frequency count 
#  on the course titles.
# 
#  Tools/Resources: You can use a “map reduce” 
#  style word counting approach.
# -----------------------------------------------

from __future__ import annotations

import csv
import json
import re
from collections import Counter
from pathlib import Path
from typing import Iterable, List


IN_TXT = Path("data/extract/course_titles.txt")
IN_JSON = Path("data/extract/course_titles.json")

OUT_DIR = Path("data/frequency")
OUT_CSV = OUT_DIR / "title_word_counts.csv"
OUT_JSON = OUT_DIR / "title_word_counts.json"

# A practical stopword list (you can add/remove as you like)
STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from",
    "in", "into", "is", "it", "of", "on", "or", "the", "to", "with",
    "without", "via", "than", "that", "this", "these", "those",
    "i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x",
    "introduction",  # optional: common but not very informative
}

# words like "topics", "seminar", etc. are sometimes too generic; optional:
OPTIONAL_GENERIC = {
    "topics", "seminar", "special", "selected", "independent", "study",
    "practicum", "workshop", "lab", "project", "capstone",
    "elective", "research",
}
# Toggle this if you want to remove generic words too
REMOVE_GENERIC_WORDS = False


def load_titles() -> List[str]:
    """
    Prefer JSON if present; otherwise read TXT (one per line).
    """
    if IN_JSON.exists():
        return json.loads(IN_JSON.read_text(encoding="utf-8"))
    if IN_TXT.exists():
        return [line.strip() for line in IN_TXT.read_text(encoding="utf-8").splitlines() if line.strip()]
    raise FileNotFoundError(
        "Could not find course titles input.\n"
        "Expected one of:\n"
        f"  - {IN_JSON}\n"
        f"  - {IN_TXT}\n"
        "Run 05_extract.py first."
    )


def tokenize(title: str) -> List[str]:
    """
    Convert a title string like:
      'AACE 6000 Arts and Culture Organizational Leadership'
    into meaningful tokens:
      ['arts', 'culture', 'organizational', 'leadership']

    Steps:
    - lowercase
    - replace punctuation with spaces
    - split on whitespace
    - remove stopwords
    - remove pure numbers (course numbers)
    """
    s = title.lower()

    # Replace anything not a letter/number with a space.
    # Keeps letters and digits; drops punctuation like ":" "," "/" "(" ")"
    s = re.sub(r"[^a-z0-9]+", " ", s)

    tokens = [t for t in s.split() if t]

    out: List[str] = []
    for t in tokens:
        # drop pure numbers (e.g., "6000", "1990")
        if t.isdigit():
            continue

        # drop stopwords
        if t in STOPWORDS:
            continue

        # optionally drop generic curriculum words
        if REMOVE_GENERIC_WORDS and t in OPTIONAL_GENERIC:
            continue

        out.append(t)

    return out


def map_phase(titles: Iterable[str]) -> List[tuple[str, int]]:
    """
    Map step: produce (word, 1) pairs for every token in every title.
    """
    pairs: List[tuple[str, int]] = []
    for title in titles:
        for word in tokenize(title):
            pairs.append((word, 1))
    return pairs


def reduce_phase(pairs: Iterable[tuple[str, int]]) -> Counter:
    """
    Reduce step: aggregate counts by summing values for each key (word).
    """
    c = Counter()
    for word, n in pairs:
        c[word] += n
    return c


def main() -> None:
    titles = load_titles()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # Map-Reduce
    pairs = map_phase(titles)
    counts = reduce_phase(pairs)

    # Sort by frequency desc, then word asc
    items = sorted(counts.items(), key=lambda x: (-x[1], x[0]))

    # Write JSON (list of objects)
    OUT_JSON.write_text(
        json.dumps([{"word": w, "count": n} for w, n in items], indent=2),
        encoding="utf-8",
    )

    # Write CSV
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["word", "count"])
        w.writeheader()
        for word, n in items:
            w.writerow({"word": word, "count": n})

    print(f"[done] Counted words from {len(titles)} titles")
    print(f"[done] CSV  -> {OUT_CSV}")
    print(f"[done] JSON -> {OUT_JSON}")

    print("\nTop 30 words:")
    for word, n in items[:30]:
        print(f"  {word:<20} {n}")


if __name__ == "__main__":
    main()
