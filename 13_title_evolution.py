# -----------------------------------------------
#  13. Title Evolution:
# 
#  Conduct a word frequency analysis 
#  on course titles from 1996 and 2024 
#  to explore shifts in academic 
#  terminology and focus areas.
# -----------------------------------------------


from __future__ import annotations

import csv
import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import matplotlib.pyplot as plt


IN_1996 = Path("10_mit_1996.json")
IN_2024 = Path("11_mit_2024.json")

OUT_DIR = Path("data/title_evolution")
OUT_CSV = OUT_DIR / "title_word_compare.csv"
OUT_PNG_2024 = OUT_DIR / "top_2024_vs_1996.png"
OUT_PNG_1996 = OUT_DIR / "top_1996_vs_2024.png"

TOP_N_PRINT = 25
TOP_N_PLOT = 20

# Stopwords: keep practical + add some catalog-generic words if desired
STOPWORDS = {
    "a","an","and","are","as","at","be","by","for","from",
    "in","into","is","it","of","on","or","the","to","with",
    "without","via","ii","iii","iv","v","vi","vii","viii",
    "ix","x","i",

    # catalog metadata words
    "units","unit","prereq","prerequisite","subject",
    "spring","fall","iap","summer","year",
    "students","student","instructor","instructors",
    "credit","credits","permission","offered","consult",
    "none","meets","limited","arranged","version",
    "staff","department","term","repeated","can","that",
    "not",
}

# Remove very short tokens (often noise)
MIN_TOKEN_LEN = 2

# Add-1 smoothing to avoid division by zero in log ratios
ALPHA = 1.0


def load_json(path: Path) -> List[dict]:
    if not path.exists():
        raise FileNotFoundError(f"Missing input: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def get_titles_1996(rows: List[dict]) -> List[str]:
    # 1996 records: {subject_number, title, ...}
    return [str(r.get("title", "")).strip() for r in rows if str(r.get("title", "")).strip()]


def get_titles_2024(rows: List[dict]) -> List[str]:
    # 2024 records: {course_id, title, ...}
    return [str(r.get("title", "")).strip() for r in rows if str(r.get("title", "")).strip()]


def tokenize_title(title: str) -> List[str]:
    """
    Convert a title into meaningful word tokens.
    - lowercase
    - remove punctuation
    - remove pure numbers
    - remove stopwords
    """
    s = title.lower()
    # replace non-alphanumeric with spaces
    s = re.sub(r"[^a-z0-9]+", " ", s)
    tokens = [t for t in s.split() if t]

    out: List[str] = []
    for t in tokens:
        if t.isdigit():
            continue
        if len(t) < MIN_TOKEN_LEN:
            continue
        if t in STOPWORDS:
            continue
        out.append(t)
    return out


def count_words(titles: Iterable[str]) -> Counter:
    c = Counter()
    for title in titles:
        for w in tokenize_title(title):
            c[w] += 1
    return c


def relative_freq(counter: Counter) -> Dict[str, float]:
    total = sum(counter.values())
    if total == 0:
        return {}
    return {w: n / total for w, n in counter.items()}


def log_ratio_shift(
    f_2024: Dict[str, float],
    f_1996: Dict[str, float],
    vocab: Iterable[str],
    alpha: float = 1.0,
) -> Dict[str, float]:
    """
    Log ratio of smoothed relative frequencies:
      shift(w) = log( (f2024(w)+alpha) / (f1996(w)+alpha) )

    Positive => more characteristic of 2024
    Negative => more characteristic of 1996
    """
    out: Dict[str, float] = {}
    for w in vocab:
        a = f_2024.get(w, 0.0) + alpha
        b = f_1996.get(w, 0.0) + alpha
        out[w] = math.log(a / b)
    return out


def write_csv(
    c96: Counter,
    c24: Counter,
    f96: Dict[str, float],
    f24: Dict[str, float],
    shift: Dict[str, float],
) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    vocab = sorted(set(c96.keys()) | set(c24.keys()))

    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=["word", "count_1996", "count_2024", "freq_1996", "freq_2024", "log_ratio_2024_vs_1996"],
        )
        w.writeheader()
        for word in vocab:
            w.writerow(
                {
                    "word": word,
                    "count_1996": int(c96.get(word, 0)),
                    "count_2024": int(c24.get(word, 0)),
                    "freq_1996": f"{f96.get(word, 0.0):.8f}",
                    "freq_2024": f"{f24.get(word, 0.0):.8f}",
                    "log_ratio_2024_vs_1996": f"{shift.get(word, 0.0):.6f}",
                }
            )


def plot_top_words(words: List[Tuple[str, float]], out_path: Path, title: str) -> None:
    labels = [w for w, _ in words]
    vals = [v for _, v in words]

    plt.figure(figsize=(10, 6))
    plt.bar(labels, vals)
    plt.title(title)
    plt.xlabel("Word")
    plt.ylabel("Log ratio (smoothed)")
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    plt.savefig(out_path, dpi=200)
    plt.close()


def main() -> None:
    data_1996 = load_json(IN_1996)
    data_2024 = load_json(IN_2024)

    titles_1996 = get_titles_1996(data_1996)
    titles_2024 = get_titles_2024(data_2024)

    c96 = count_words(titles_1996)
    c24 = count_words(titles_2024)

    f96 = relative_freq(c96)
    f24 = relative_freq(c24)

    vocab = set(c96.keys()) | set(c24.keys())
    shift = log_ratio_shift(f24, f96, vocab, alpha=ALPHA)

    # rank shifts
    more_2024 = sorted(shift.items(), key=lambda x: x[1], reverse=True)
    more_1996 = sorted(shift.items(), key=lambda x: x[1])

    # write CSV
    write_csv(c96, c24, f96, f24, shift)

    # plots
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    plot_top_words(more_2024[:TOP_N_PLOT], OUT_PNG_2024, f"Words more characteristic of 2024 (top {TOP_N_PLOT})")
    plot_top_words(more_1996[:TOP_N_PLOT], OUT_PNG_1996, f"Words more characteristic of 1996 (top {TOP_N_PLOT})")

    # print summary
    print(f"[done] 1996 titles: {len(titles_1996)} | unique words: {len(c96)}")
    print(f"[done] 2024 titles: {len(titles_2024)} | unique words: {len(c24)}")
    print(f"[done] CSV  -> {OUT_CSV}")
    print(f"[done] Plots -> {OUT_PNG_2024}, {OUT_PNG_1996}")

    print("\n=== Top words (raw frequency) ===")
    print("1996:", c96.most_common(15))
    print("2024:", c24.most_common(15))

    print(f"\n=== Words most associated with 2024 (by log ratio, top {TOP_N_PRINT}) ===")
    for w, s in more_2024[:TOP_N_PRINT]:
        print(f"  {w:<18} log_ratio={s:>8.3f}  (1996={c96.get(w,0)}, 2024={c24.get(w,0)})")

    print(f"\n=== Words most associated with 1996 (by log ratio, top {TOP_N_PRINT}) ===")
    for w, s in more_1996[:TOP_N_PRINT]:
        print(f"  {w:<18} log_ratio={s:>8.3f}  (1996={c96.get(w,0)}, 2024={c24.get(w,0)})")

    print("\nInterpretation tips:")
    print("- 2024-shifted words often reflect newer fields/terminology (e.g., data, machine, autonomous, computational).")
    print("- 1996-shifted words may reflect older curriculum emphases or naming conventions.")
    print("- Changes also reflect catalog granularity: modern catalogs list more specialized topics and seminars.")


if __name__ == "__main__":
    main()