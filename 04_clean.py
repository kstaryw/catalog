# -----------------------------------------------
#   4. Data Cleaning:
# 
#   Objective: Clean and preprocess the 
#   extracted data for analysis.
# 
#   Tools/Resources: Use Regular Expressions 
#   or string manipulation functions in 
#   your programming language.
# -----------------------------------------------
from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple


IN_JSON = Path("data/parsed/ne_courses.json")
OUT_DIR = Path("data/clean")
OUT_JSON = OUT_DIR / "ne_courses_clean.json"
OUT_CSV = OUT_DIR / "ne_courses_clean.csv"


@dataclass
class CleanCourse:
    subject_file: str
    subject: str                 # e.g. "CS"
    number: str                  # e.g. "2500"
    course_code: str             # e.g. "CS 2500" (normalized)
    title: str
    description: str
    credits_raw: Optional[str]   # original credits string
    credits_min: Optional[float]
    credits_max: Optional[float]


# ---------- basic cleaners ----------

def clean_ws(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip()


def normalize_course_code(course_code: str) -> Tuple[str, str, str]:
    """
    Normalize course code into (subject, number, normalized_code).
    Accepts strings like:
      "CS 2500", "CS2500", "MATH 1341A"
    Returns empty strings if it can't parse.
    """
    cc = clean_ws(course_code).upper()

    m = re.match(r"^([A-Z]{2,6})\s*[- ]?\s*(\d{3,5}[A-Z]?)$", cc)
    if not m:
        return "", "", cc

    subj = m.group(1)
    num = m.group(2)
    norm = f"{subj} {num}"
    return subj, num, norm


def parse_credits(credits_raw: Optional[str]) -> Tuple[Optional[float], Optional[float]]:
    """
    Convert credits strings into numeric min/max.
    Examples:
      "3 Hours" -> (3.0, 3.0)
      "4 SH" -> (4.0, 4.0)
      "1-4 Hours" -> (1.0, 4.0)
      "0-1 Credits" -> (0.0, 1.0)
      None / "" -> (None, None)
    """
    if not credits_raw:
        return None, None

    s = clean_ws(credits_raw)
    s = s.replace("–", "-")  # normalize en-dash to hyphen

    # Pull all numbers (including decimals) in order
    nums = re.findall(r"\d+(?:\.\d+)?", s)
    if not nums:
        return None, None

    # If it looks like a range "1-4"
    if "-" in s and len(nums) >= 2:
        try:
            lo = float(nums[0])
            hi = float(nums[1])
            return (min(lo, hi), max(lo, hi))
        except ValueError:
            return None, None

    # Otherwise treat first number as exact credits
    try:
        v = float(nums[0])
        return v, v
    except ValueError:
        return None, None


def drop_html_if_any(text: str) -> str:
    """
    Your parser already extracted text, but in case any HTML leaked in,
    remove tags defensively.
    """
    t = text or ""
    t = re.sub(r"<[^>]+>", " ", t)  # remove tags
    return clean_ws(t)


def canonical_title(title: str) -> str:
    """
    Make titles consistent (remove trailing periods/spaces).
    """
    t = clean_ws(title)
    t = re.sub(r"\s+\.$", ".", t)
    # remove a single trailing period if it's just punctuation noise
    if t.endswith("."):
        t = t[:-1].strip()
    return t


# ---------- main cleaning pipeline ----------

def main() -> None:
    if not IN_JSON.exists():
        raise FileNotFoundError(
            f"Missing parsed JSON: {IN_JSON}\n"
            "Run 03_parse.py first."
        )

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    data = json.loads(IN_JSON.read_text(encoding="utf-8"))

    cleaned: list[CleanCourse] = []
    seen_keys: set[tuple] = set()

    for row in data:
        subject_file = clean_ws(row.get("subject_file", ""))
        course_code_raw = clean_ws(row.get("course_code", ""))
        title_raw = row.get("title", "")
        desc_raw = row.get("description", "")
        credits_raw = row.get("credits")

        # Clean text fields
        title = canonical_title(drop_html_if_any(str(title_raw)))
        description = drop_html_if_any(str(desc_raw))

        # Normalize course code
        subject, number, course_code = normalize_course_code(course_code_raw)

        # If we can't parse a real course code, skip (prevents breaking analysis)
        if not subject or not number:
            continue

        # Parse credits range
        cmin, cmax = parse_credits(credits_raw if credits_raw is None else str(credits_raw))

        # Deduplicate (same course code + title)
        key = (subject, number, title.lower())
        if key in seen_keys:
            continue
        seen_keys.add(key)

        cleaned.append(
            CleanCourse(
                subject_file=subject_file,
                subject=subject,
                number=number,
                course_code=course_code,
                title=title,
                description=description,
                credits_raw=clean_ws(str(credits_raw)) if credits_raw is not None else None,
                credits_min=cmin,
                credits_max=cmax,
            )
        )

    # Write clean JSON
    OUT_JSON.write_text(
        json.dumps([c.__dict__ for c in cleaned], indent=2),
        encoding="utf-8",
    )

    # Write clean CSV
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "subject_file",
                "subject",
                "number",
                "course_code",
                "title",
                "description",
                "credits_raw",
                "credits_min",
                "credits_max",
            ],
        )
        writer.writeheader()
        for c in cleaned:
            writer.writerow(c.__dict__)

    print(f"[done] Cleaned courses: {len(cleaned)}")
    print(f"[done] JSON -> {OUT_JSON}")
    print(f"[done] CSV  -> {OUT_CSV}")

    # quick sanity checks
    # 1) how many have missing credits?
    missing_credits = sum(1 for c in cleaned if c.credits_min is None)
    print(f"[info] Missing credits: {missing_credits}")

    # 2) show a few examples with ranges
    ranged = [c for c in cleaned if c.credits_min is not None and c.credits_max is not None and c.credits_min != c.credits_max]
    for ex in ranged[:5]:
        print(f"  [range] {ex.course_code}: {ex.credits_raw} -> ({ex.credits_min}, {ex.credits_max})")


if __name__ == "__main__":
    main()