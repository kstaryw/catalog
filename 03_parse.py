# -----------------------------------------------
#   3. Data Parsing:
# 
#   Objective: Parse course data leveraging
#   HTML elements structure.
# 
#   Tools/Resources: Use resources like the 
#   DOMParser, BeautifulSoup, or Regular Expressions.
#       Beautiful Soup:
#           https://www.crummy.com/software/BeautifulSoup/
#       DOMParser:
#           https://developer.mozilla.org/en-US/docs/Web/API/DOMParser
#       RegEx:
#           https://regexr.com 
#           https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide/Regular_expressions
# -----------------------------------------------


from __future__ import annotations

import csv
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional, Tuple

from bs4 import BeautifulSoup, Tag

# input from 02_combine.py
COMBINED_HTML = Path("data/combined/ne_course_catalog_combined.html")

# outputs for parsed structured data
OUT_DIR = Path("data/parsed")
OUT_JSON = OUT_DIR / "ne_courses.json"
OUT_CSV = OUT_DIR / "ne_courses.csv"


@dataclass
class Course:
    subject_file: str            # e.g. "arch.html" (from data-source-file)
    course_code: str             # e.g. "ARCH 1110"
    title: str                   # e.g. "Architecture Design Fundamentals"
    credits: Optional[str]       # may be None
    description: str
    raw_title: str               # keep original for debugging/provenance


# ---------------- helpers ----------------

def clean_text(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def split_title_line(title_line: str) -> Tuple[str, str, Optional[str]]:
    """
    Parse a course title line into: (course_code, title, credits)

    Handles common patterns like:
      "ARCH 1110. Title (4 Hours)"
      "CS 2500 Title 4 SH"
      "MATH 1341. Title (4)"
    If it can't detect credits, credits=None.
    If it can't detect a code, returns ("", title_line, credits).
    """
    t = clean_text(title_line)
    credits = None

    # credits at end in parentheses
    m = re.search(r"\(([^()]*\d+[^()]*)\)\s*$", t)
    if m:
        credits = clean_text(m.group(1))
        t = clean_text(t[: m.start()])

    # credits at end without parentheses e.g. "4 SH"
    if credits is None:
        m2 = re.search(r"\b(\d+(?:\.\d+)?)\s*(SH|Hours|Hrs|Credits?)\s*$", t, flags=re.I)
        if m2:
            credits = clean_text(m2.group(0))
            t = clean_text(t[: m2.start()])

    # course code: "ARCH 1110" or "CS 2500"
    m3 = re.match(r"^([A-Z]{2,6})\s+(\d{3,5}[A-Z]?)\b[.\s-]*", t)
    if not m3:
        # sometimes compressed like "ARCH1110"
        m4 = re.match(r"^([A-Z]{2,6})(\d{3,5}[A-Z]?)\b[.\s-]*", t)
        if m4:
            code = f"{m4.group(1)} {m4.group(2)}"
            title = clean_text(t[m4.end():])
            return code, title, credits
        return "", t, credits

    code = f"{m3.group(1)} {m3.group(2)}"
    title = clean_text(t[m3.end():])
    return code, title, credits


def find_course_blocks(section: Tag) -> list[Tag]:
    """
    NE catalog (Modern Campus) often uses div.courseblock wrappers.
    We try that first; if missing, fall back to .courseblocktitle nodes.
    """
    blocks = section.select("div.courseblock")
    if blocks:
        return blocks

    # fallback: if no wrapper, use each title node's parent as a "block"
    titles = section.select(".courseblocktitle")
    if titles:
        out: list[Tag] = []
        for t in titles:
            out.append(t.parent if isinstance(t.parent, Tag) else t)
        return out

    return []


def extract_title_and_desc(block: Tag) -> Tuple[str, str]:
    """
    Extract a raw title line and a description from a course block.
    """
    title_tag = block.select_one(".courseblocktitle")
    raw_title = clean_text(title_tag.get_text(" ", strip=True)) if title_tag else ""

    desc_tag = block.select_one(".courseblockdesc")
    desc = clean_text(desc_tag.get_text(" ", strip=True)) if desc_tag else ""

    # fallback: if we have a title but no desc node, take remaining text
    if raw_title and not desc:
        full = clean_text(block.get_text(" ", strip=True))
        if full.startswith(raw_title):
            desc = clean_text(full[len(raw_title):])
        else:
            desc = full

    return raw_title, desc


# ---------------- main ----------------

def main() -> None:
    if not COMBINED_HTML.exists():
        raise FileNotFoundError(
            f"Missing combined HTML: {COMBINED_HTML}\n"
            "Run 02_combine.py first."
        )

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    html = COMBINED_HTML.read_text(encoding="utf-8", errors="replace")
    soup = BeautifulSoup(html, "html.parser")

    # created by 02_combine.py: <section class="subject-page" data-source-file="arch.html">
    sections = soup.select("section.subject-page[data-source-file]")
    if not sections:
        raise RuntimeError(
            "Could not find subject sections.\n"
            "This parser expects 02_combine.py to wrap each file in:\n"
            "<section class='subject-page' data-source-file='...'>"
        )

    courses: list[Course] = []

    for section in sections:
        source_file = (section.get("data-source-file") or "").strip()
        blocks = find_course_blocks(section)

        for block in blocks:
            raw_title, desc = extract_title_and_desc(block)
            if not raw_title:
                continue

            code, title, credits = split_title_line(raw_title)

            # skip items that don't look like a course
            if not code:
                continue

            courses.append(
                Course(
                    subject_file=source_file,
                    course_code=code,
                    title=title,
                    credits=credits,
                    description=desc,
                    raw_title=raw_title,
                )
            )

    # write JSON
    OUT_JSON.write_text(json.dumps([asdict(c) for c in courses], indent=2), encoding="utf-8")

    # write CSV
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["subject_file", "course_code", "title", "credits", "description", "raw_title"],
        )
        writer.writeheader()
        for c in courses:
            writer.writerow(asdict(c))

    print(f"[done] Parsed {len(courses)} courses")
    print(f"[done] JSON -> {OUT_JSON}")
    print(f"[done] CSV  -> {OUT_CSV}")

    # quick sanity preview
    for c in courses[:5]:
        print(f"  - {c.course_code}: {c.title} ({c.credits})")


if __name__ == "__main__":
    main()
