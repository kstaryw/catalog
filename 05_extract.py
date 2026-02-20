# -----------------------------------------------
#  5. Data Extraction:
# 
#  Objective: Extract course titles from 
#  the data you cleaned.
# -----------------------------------------------
#   Methodology:
#   - Read cleaned JSON produced by 04_clean.py
#   - Identify each record's normalized course_code
#     and title fields
#   - Construct a single "course title" string:
#       "<course_code> <title>"
#   - Deduplicate while preserving order
#   - Write results to TXT/JSON/CSV for later use
# -----------------------------------------------

from __future__ import annotations

import csv
import json
from pathlib import Path


IN_JSON = Path("data/clean/ne_courses_clean.json")
OUT_DIR = Path("data/extract")

OUT_TXT = OUT_DIR / "course_titles.txt"
OUT_JSON = OUT_DIR / "course_titles.json"
OUT_CSV = OUT_DIR / "course_titles.csv"


def main() -> None:
    if not IN_JSON.exists():
        raise FileNotFoundError(
            f"Missing cleaned dataset: {IN_JSON}\n"
            "Run 04_clean.py first."
        )

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    data = json.loads(IN_JSON.read_text(encoding="utf-8"))

    titles: list[str] = []
    rows: list[dict] = []
    seen: set[str] = set()

    for r in data:
        # Robustly access fields from cleaned data
        course_code = (r.get("course_code") or "").strip()
        title = (r.get("title") or "").strip()

        # Rule to avoid pitfalls:
        # - must have both a course code and a title
        if not course_code or not title:
            continue

        combined = f"{course_code} {title}"

        # Deduplicate (some catalogs can repeat cross-listed courses)
        if combined in seen:
            continue
        seen.add(combined)

        titles.append(combined)
        rows.append(
            {
                "course_code": course_code,
                "title": title,
                "course_title": combined,
            }
        )

    # Write TXT (one per line)
    OUT_TXT.write_text("\n".join(titles) + "\n", encoding="utf-8")

    # Write JSON (list of strings)
    OUT_JSON.write_text(json.dumps(titles, indent=2), encoding="utf-8")

    # Write CSV (structured)
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["course_code", "title", "course_title"])
        w.writeheader()
        for row in rows:
            w.writerow(row)

    print(f"[done] Extracted {len(titles)} unique course titles")
    print(f"[done] TXT  -> {OUT_TXT}")
    print(f"[done] JSON -> {OUT_JSON}")
    print(f"[done] CSV  -> {OUT_CSV}")

    # Preview
    for t in titles[:10]:
        print("  -", t)


if __name__ == "__main__":
    main()