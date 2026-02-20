# -----------------------------------------------
#  11. Catalog 2024
# 
#  Extract course data from the current 
#  MIT course catalog. After extracting the 
#  text, create a data model and save the 
#  processed data.
# -----------------------------------------------

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup, Tag


BASE = "https://catalog.mit.edu"
SUBJECTS_INDEX = f"{BASE}/subjects/"
OUT_JSON = Path("11_mit_2024.json")

# be polite
SLEEP_SECONDS = 0.25
TIMEOUT = 30

# Matches common MIT subject IDs:
#  - 6.1000
#  - 21H.001
#  - CMS.100
#  - 11.001 (etc.)
COURSE_HEADER_RE = re.compile(
    r"^\s*([0-9A-Z]{1,4}(?:\.[0-9A-Z]{1,4})+)\s+(.+?)\s*$"
)


@dataclass
class MITCourse:
    course_id: str
    title: str
    description: str
    prereq: Optional[str]
    units: Optional[str]
    instructors: Optional[str]
    department_page: str             # e.g., "Electrical Engineering and Computer Science (Course 6)"
    source_url: str


def get(url: str) -> str:
    r = requests.get(url, timeout=TIMEOUT, headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    return r.text


def clean_text(s: str) -> str:
    s = re.sub(r"\s+", " ", s or "").strip()
    return s


def peel_embedded_fields(text: str) -> tuple[str, Optional[str], Optional[str], Optional[str]]:
    """
    Extract embedded prereq / level-term / units from mixed text.
    Then remove 'Subject meets with ...' prefix if it remains.
    Returns: (clean_description, prereq, level_term, units)
    """
    s = clean_text(text)

    prereq = None
    level_term = None
    units = None

    # 1) Extract Prereq first (before removing any prefix)
    m = re.search(
        r"\bPrereq:\s*(.+?)(?=(\b[UG]\s*\(|\b\d+\s*-\s*\d+\s*-\s*\d+\s*units\b|\b\d+\s*units\b|$))",
        s,
        flags=re.I,
    )
    if m:
        prereq = clean_text(m.group(1))
        s = clean_text(s[:m.start()] + " " + s[m.end():])

    # 2) Extract level/term like "U (Spring)" or "G (Fall, Spring)"
    m = re.search(r"\b([UG])\s*\(([^)]+)\)\b", s)
    if m:
        level_term = clean_text(f"{m.group(1)} ({m.group(2)})")
        s = clean_text(s[:m.start()] + " " + s[m.end():])

    # 3) Extract units like "3-2-7 units" or "12 units"
    m = re.search(r"\b(\d+\s*-\s*\d+\s*-\s*\d+\s*units|\d+\s*units)\b", s, flags=re.I)
    if m:
        units = clean_text(m.group(1))
        s = clean_text(s[:m.start()] + " " + s[m.end():])

    # 4) Now remove leading "Subject meets with ..." if present.
    # We remove up to the first strong narrative verb to avoid eating real content.
    s = re.sub(
        r"^\s*Subject meets with\b.*?(?=\b(Presents|Introduces|Provides|Covers|Explores|Develops|Focuses|Examines|Studies|Designs|Addresses)\b)",
        "",
        s,
        flags=re.I,
    )
    s = clean_text(s)

    # 5) Clean punctuation artifacts after deletions
    s = re.sub(r"\s+\.\s+", " ", s)
    s = clean_text(s)

    return s, prereq, level_term, units


def extract_subject_urls(index_html: str) -> List[str]:
    soup = BeautifulSoup(index_html, "html.parser")
    urls: List[str] = []
    for a in soup.select("a[href]"):
        href = a.get("href", "").strip()
        # Keep only subject pages under /subjects/<slug>/
        if href.startswith("/subjects/") and href.count("/") >= 3:
            # exclude PDFs and the index itself
            if href.endswith(".pdf") or href == "/subjects/":
                continue
            urls.append(urljoin(BASE, href))

    # Deduplicate while preserving order
    seen = set()
    out: List[str] = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


def pick_main_container(soup: BeautifulSoup) -> Tag:
    # Try a few common containers; fall back to body.
    for sel in ["#content", "main", ".page_content", ".container", "body"]:
        node = soup.select_one(sel)
        if node:
            return node
    return soup.body  # type: ignore


def iter_text_blocks(container: Tag) -> List[Tag]:
    """
    Return an ordered list of tags that commonly contain content.
    We keep headers + paragraphs + lists, in document order.
    """
    tags = container.find_all(["h2", "h3", "h4", "p", "ul", "ol", "div"], recursive=True)

    # Filter out huge nav/sidebars by skipping tags with clearly irrelevant roles/classes
    out: List[Tag] = []
    for t in tags:
        cls = " ".join(t.get("class", [])) if isinstance(t.get("class", []), list) else str(t.get("class", ""))
        role = str(t.get("role", ""))
        if "nav" in cls.lower() or role.lower() == "navigation":
            continue
        out.append(t)
    return out


def parse_course_page(url: str) -> List[MITCourse]:
    html = get(url)
    soup = BeautifulSoup(html, "html.parser")

    # department/program title (page H1 is usually descriptive)
    h1 = soup.find(["h1", "h2"])
    dept_title = clean_text(h1.get_text(" ", strip=True)) if h1 else clean_text(url.split("/")[-2])

    container = pick_main_container(soup)
    blocks = iter_text_blocks(container)

    courses: List[MITCourse] = []
    current: Optional[Dict[str, Any]] = None
    desc_lines: List[str] = []

    def flush():
        nonlocal current, desc_lines
        if not current:
            return
        description_raw = clean_text(" ".join(desc_lines))
        description_clean, prereq2, _, units2 = peel_embedded_fields(description_raw)

        # Only fill fields if not already captured
        if current.get("prereq") is None and prereq2:
            current["prereq"] = prereq2
        if current.get("units") is None and units2:
            current["units"] = units2

        description = description_clean
        courses.append(
            MITCourse(
                course_id=current["course_id"],
                title=current["title"],
                description=description,
                prereq=current.get("prereq"),
                units=current.get("units"),
                instructors=current.get("instructors"),
                department_page=dept_title,
                source_url=url,
            )
        )
        current = None
        desc_lines = []

    for t in blocks:
        text = clean_text(t.get_text(" ", strip=True))
        if not text:
            continue

        # Detect a course header line
        m = COURSE_HEADER_RE.match(text)
        if m:
            # Start of a new course
            flush()
            current = {
                "course_id": m.group(1),
                "title": m.group(2),
                "prereq": None,
                "units": None,
                "instructors": None,
            }
            continue

        # If we are inside a course, classify lines
        if current is not None:
            # Examples on the site often show lines like:
            # "Prereq: None", "U (IAP)", "2-2-2 units", "Staff"
            if text.lower().startswith("prereq:"):
                current["prereq"] = clean_text(text[len("prereq:"):])
                continue

            # units line often ends with "units"
            if text.lower().endswith(" units") or "units arranged" in text.lower():
                current["units"] = text
                continue

            # level/term line often looks like "U (IAP)" or "G (Fall, Spring)"
            if re.fullmatch(r"[UG]\s*\(.+\)", text):
                continue

            # instructor line: many pages use names or "Staff" (not perfect, but useful)
            # If the line is short-ish and looks like names, record it.
            if len(text) <= 80 and (
                text.lower() == "staff"
                or re.search(r"[A-Z]\.\s*[A-Z][a-z]", text)  # "A. Madry"
                or "," in text
            ):
                # don't overwrite if we already captured instructors
                if current.get("instructors") is None:
                    current["instructors"] = text
                    continue

            # otherwise treat as description content
            desc_lines.append(text)

    flush()

    # Remove entries that accidentally matched non-course headers
    courses = [c for c in courses if c.course_id and c.title]
    return courses


def main() -> None:
    print(f"[info] Fetching subjects index: {SUBJECTS_INDEX}")
    index_html = get(SUBJECTS_INDEX)
    subject_urls = extract_subject_urls(index_html)
    print(f"[info] Found {len(subject_urls)} subject pages")

    all_courses: List[MITCourse] = []
    for i, url in enumerate(subject_urls, start=1):
        try:
            time.sleep(SLEEP_SECONDS)
            courses = parse_course_page(url)
            all_courses.extend(courses)
            print(f"[done] ({i}/{len(subject_urls)}) {url} -> {len(courses)} courses")
        except Exception as e:
            print(f"[warn] Failed {url}: {e}")

    # Deduplicate by (course_id, title) just in case
    dedup: Dict[Tuple[str, str], MITCourse] = {}
    for c in all_courses:
        key = (c.course_id, c.title.strip().lower())
        if key not in dedup:
            dedup[key] = c

    final_list = [asdict(v) for v in dedup.values()]
    final_list.sort(key=lambda x: (x["course_id"], x["title"].lower()))

    OUT_JSON.write_text(json.dumps(final_list, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[final] Wrote {len(final_list)} unique courses -> {OUT_JSON}")


if __name__ == "__main__":
    main()
